"""Compliance-Llama FastAPI gateway.

Endpoints
---------
GET  /health                — liveness + vLLM reachability
POST /v1/generate           — single-shot generation (returns full SOP)
POST /v1/generate/stream    — Server-Sent Events streaming
POST /v1/compare            — side-by-side base vs fine-tuned
POST /v1/export/pdf         — render a generated SOP to PDF

The gateway is deliberately thin. All model logic lives in vLLM.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .config import settings
from .prompts import build_messages
from .schemas import (
    CompareResponse,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
)
from .vllm_client import VLLMClient, VLLMError
from .pdf import render_sop_to_pdf
from pydantic import BaseModel


logger = logging.getLogger("compliance-llama.api")
logging.basicConfig(level=settings.log_level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.vllm = VLLMClient(settings.vllm_base_url, timeout_s=settings.request_timeout_s)
    app.state.base_vllm = (
        VLLMClient(settings.base_llama_url, timeout_s=settings.request_timeout_s)
        if settings.base_llama_url else None
    )
    logger.info("Compliance-Llama gateway ready. vLLM=%s base=%s",
                settings.vllm_base_url, settings.base_llama_url or "<disabled>")
    try:
        yield
    finally:
        await app.state.vllm.aclose()
        if app.state.base_vllm is not None:
            await app.state.base_vllm.aclose()


app = FastAPI(
    title="Compliance-Llama API",
    description="Audit-ready SOP and QMS generation for MedTech, served from a "
                "QLoRA fine-tune of Llama 3.1 70B running on AMD MI300X.",
    version="0.1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    reachable = await app.state.vllm.health()
    return HealthResponse(
        status="ok" if reachable else "degraded",
        vllm_reachable=reachable,
        fine_tuned_model=settings.fine_tuned_model,
    )


def _capped(req: GenerateRequest) -> int:
    return min(req.max_tokens, settings.max_output_tokens)


@app.post("/v1/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    messages = build_messages(req.device.render(), req.instruction())
    started = time.perf_counter()
    try:
        result = await app.state.vllm.chat_complete(
            model=settings.fine_tuned_model,
            messages=messages,
            temperature=req.temperature,
            max_tokens=_capped(req),
        )
    except VLLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    choice = result["choices"][0]
    content = choice["message"]["content"]
    usage = result.get("usage", {})

    return GenerateResponse(
        artifact=req.artifact,
        model=settings.fine_tuned_model,
        content=content,
        output_tokens=int(usage.get("completion_tokens", 0)),
        latency_ms=int((time.perf_counter() - started) * 1000),
    )


@app.post("/v1/generate/stream")
async def generate_stream(req: GenerateRequest) -> EventSourceResponse:
    messages = build_messages(req.device.render(), req.instruction())

    async def event_source():
        try:
            async for delta in app.state.vllm.chat_stream(
                model=settings.fine_tuned_model,
                messages=messages,
                temperature=req.temperature,
                max_tokens=_capped(req),
            ):
                yield {"event": "token", "data": delta}
            yield {"event": "done", "data": "ok"}
        except VLLMError as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_source(), ping=15)


@app.post("/v1/compare", response_model=CompareResponse)
async def compare(req: GenerateRequest) -> CompareResponse:
    if app.state.base_vllm is None:
        raise HTTPException(
            status_code=503,
            detail="No base-model endpoint configured. Set BASE_LLAMA_URL to enable comparison.",
        )

    messages = build_messages(req.device.render(), req.instruction())
    capped = _capped(req)

    started_ft = time.perf_counter()
    ft = await app.state.vllm.chat_complete(
        settings.fine_tuned_model, messages, req.temperature, capped
    )
    ft_latency = int((time.perf_counter() - started_ft) * 1000)

    started_base = time.perf_counter()
    base = await app.state.base_vllm.chat_complete(
        settings.base_model, messages, req.temperature, capped
    )
    base_latency = int((time.perf_counter() - started_base) * 1000)

    def _to_resp(payload: dict, model_name: str, latency: int) -> GenerateResponse:
        choice = payload["choices"][0]
        usage = payload.get("usage", {})
        return GenerateResponse(
            artifact=req.artifact,
            model=model_name,
            content=choice["message"]["content"],
            output_tokens=int(usage.get("completion_tokens", 0)),
            latency_ms=latency,
        )

    return CompareResponse(
        fine_tuned=_to_resp(ft, settings.fine_tuned_model, ft_latency),
        base=_to_resp(base, settings.base_model, base_latency),
    )


class PDFExportRequest(BaseModel):
    content: str
    device_name: str = "Device"
    artifact: str = "SOP"


@app.post("/v1/export/pdf")
async def export_pdf(req: PDFExportRequest) -> Response:
    pdf = render_sop_to_pdf(req.content, device_name=req.device_name, artifact=req.artifact)
    safe_name = req.device_name.replace(" ", "_")
    filename = f"compliance-llama-{req.artifact}-{safe_name}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
