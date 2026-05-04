"""Throughput / latency benchmark for the Compliance-Llama vLLM endpoint.

Hits the OpenAI-compatible /v1/completions endpoint and reports:
  - tokens/sec (output)
  - tokens/sec (combined)
  - time-to-first-token (median, p99)
  - request throughput at a chosen concurrency

Usage:
    python serving/benchmark.py --concurrency 16 --requests 64
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field

import httpx


SAMPLE_PROMPT = (
    "Draft a CAPA SOP for a Class II infusion pump used in patient homes, "
    "with explicit ISO 13485 and 21 CFR 820 citations."
)


@dataclass
class RequestResult:
    ttft_s: float
    total_s: float
    output_tokens: int
    prompt_tokens: int
    error: str | None = None


@dataclass
class Summary:
    results: list[RequestResult] = field(default_factory=list)

    def report(self) -> None:
        ok = [r for r in self.results if r.error is None]
        if not ok:
            print("All requests failed.")
            return

        ttfts = [r.ttft_s for r in ok]
        totals = [r.total_s for r in ok]
        out_tokens = sum(r.output_tokens for r in ok)
        all_tokens = out_tokens + sum(r.prompt_tokens for r in ok)
        wall = max(totals)

        print(f"Successful requests: {len(ok)} / {len(self.results)}")
        print(f"Wall time:           {wall:.2f}s")
        print(f"Output tok/s:        {out_tokens / wall:.1f}")
        print(f"Total tok/s:         {all_tokens / wall:.1f}")
        print(f"TTFT  median / p99:  {statistics.median(ttfts):.3f}s / {_p99(ttfts):.3f}s")
        print(f"Total median / p99:  {statistics.median(totals):.3f}s / {_p99(totals):.3f}s")


def _p99(xs: list[float]) -> float:
    if not xs:
        return 0.0
    xs_sorted = sorted(xs)
    return xs_sorted[min(len(xs_sorted) - 1, int(0.99 * len(xs_sorted)))]


async def _one(client: httpx.AsyncClient, base_url: str, max_tokens: int) -> RequestResult:
    payload = {
        "model": "compliance-llama-70b",
        "prompt": SAMPLE_PROMPT,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": True,
    }
    started = time.perf_counter()
    ttft: float | None = None
    output_tokens = 0
    prompt_tokens = 0

    try:
        async with client.stream("POST", f"{base_url}/v1/completions", json=payload, timeout=120) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                if ttft is None:
                    ttft = time.perf_counter() - started
                event = json.loads(data)
                output_tokens += 1
                if event.get("usage"):
                    prompt_tokens = event["usage"].get("prompt_tokens", 0)
    except Exception as e:  # noqa: BLE001
        return RequestResult(0, 0, 0, 0, error=str(e))

    return RequestResult(
        ttft_s=ttft or 0.0,
        total_s=time.perf_counter() - started,
        output_tokens=output_tokens,
        prompt_tokens=prompt_tokens,
    )


async def run(base_url: str, requests: int, concurrency: int, max_tokens: int) -> Summary:
    sem = asyncio.Semaphore(concurrency)
    summary = Summary()

    async with httpx.AsyncClient() as client:
        async def task() -> None:
            async with sem:
                summary.results.append(await _one(client, base_url, max_tokens))

        await asyncio.gather(*(task() for _ in range(requests)))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=32)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--max-tokens", type=int, default=512)
    args = parser.parse_args()

    summary = asyncio.run(run(args.base_url, args.requests, args.concurrency, args.max_tokens))
    summary.report()


if __name__ == "__main__":
    main()
