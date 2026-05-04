"""Runtime configuration for the FastAPI gateway."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    vllm_base_url: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
    base_llama_url: str = os.getenv("BASE_LLAMA_URL", "")  # optional comparison endpoint
    fine_tuned_model: str = os.getenv("FINE_TUNED_MODEL", "compliance-llama-70b")
    base_model: str = os.getenv("BASE_MODEL", "llama-3.1-70b-instruct")
    request_timeout_s: float = float(os.getenv("REQUEST_TIMEOUT_S", "300"))
    log_level: str = os.getenv("CL_LOG_LEVEL", "INFO")
    max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000",
        ).split(",") if o.strip()
    )


settings = Settings()
