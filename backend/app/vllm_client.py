"""Thin async client over the vLLM OpenAI-compatible API.

We deliberately don't import the official OpenAI SDK — vLLM diverges in a few
places (token counts, finish reasons), and a minimal client lets us own the
SSE transformation that the frontend consumes.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

logger = logging.getLogger("compliance-llama.vllm")


class VLLMError(RuntimeError):
    pass


class VLLMClient:
    def __init__(self, base_url: str, timeout_s: float = 300.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            r = await self._client.get(f"{self._base_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    async def chat_complete(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        r = await self._client.post(f"{self._base_url}/v1/chat/completions", json=payload)
        if r.status_code >= 400:
            raise VLLMError(f"vLLM error {r.status_code}: {r.text[:500]}")
        return r.json()

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Yield raw delta strings from the vLLM stream."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with self._client.stream(
            "POST", f"{self._base_url}/v1/chat/completions", json=payload
        ) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise VLLMError(f"vLLM stream error {resp.status_code}: {body[:500]!r}")

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    return
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed SSE chunk: %r", data[:120])
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {}).get("content")
                if delta:
                    yield delta
