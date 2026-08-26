#!/usr/bin/env python3
"""Benchmark: compare direct Ollama vs ModelRelay gateway latency.

Usage:
    python scripts/benchmark.py --n 5 --key mr_xxx
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    return sorted(values)[min(len(values) - 1, int(len(values) * p))]


async def _measure_stream(client: httpx.AsyncClient, url: str, payload: dict, headers: dict | None) -> dict:
    start = time.perf_counter()
    first_token: float | None = None
    output_bytes = 0
    async with client.stream("POST", url, json=payload, headers=headers) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.strip():
                continue
            if first_token is None:
                first_token = time.perf_counter()
            output_bytes += len(line)
    total = time.perf_counter()
    return {
        "first_token_ms": round((first_token - start) * 1000, 1) if first_token else None,
        "total_ms": round((total - start) * 1000, 1),
        "output_bytes": output_bytes,
    }


async def _run(client: httpx.AsyncClient, url: str, payload: dict, headers: dict | None, n: int) -> dict:
    results = [await _measure_stream(client, url, payload, headers) for _ in range(n)]
    ft = [r["first_token_ms"] for r in results if r["first_token_ms"] is not None]
    tot = [r["total_ms"] for r in results]
    return {
        "n": len(results),
        "first_token_p50": _pct(ft, 0.5),
        "first_token_p95": _pct(ft, 0.95),
        "total_p50": _pct(tot, 0.5),
        "total_p95": _pct(tot, 0.95),
    }


async def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark direct Ollama vs ModelRelay gateway")
    p.add_argument("--prompt", default="Explain how TCP works in three sentences.")
    p.add_argument("--model", default="qwen2.5-coder:7b", help="real model name for direct Ollama")
    p.add_argument("--gateway-model", default="local-coder", help="logical model name for the gateway")
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--ollama", default="http://127.0.0.1:11434")
    p.add_argument("--gateway", default="http://127.0.0.1:8000")
    p.add_argument("--key", default="", help="gateway x-api-key (required if auth enabled)")
    args = p.parse_args()

    ollama_payload = {"model": args.model, "prompt": args.prompt, "stream": True}
    gateway_payload = {
        "model": args.gateway_model,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": args.prompt}],
        "stream": True,
    }
    headers = {"x-api-key": args.key} if args.key else None

    async with httpx.AsyncClient(timeout=180) as client:
        print(f"Direct Ollama  {args.ollama}/api/chat  (model={args.model})")
        direct = await _run(client, f"{args.ollama}/api/chat", ollama_payload, None, args.n)
        print(f"  {direct}\n")

        print(f"Gateway        {args.gateway}/v1/messages  (model={args.gateway_model})")
        gw = await _run(client, f"{args.gateway}/v1/messages", gateway_payload, headers, args.n)
        print(f"  {gw}\n")

        if direct["first_token_p50"] is not None and gw["first_token_p50"] is not None:
            print(f"First-token overhead p50: {gw['first_token_p50'] - direct['first_token_p50']:.1f} ms")


if __name__ == "__main__":
    asyncio.run(main())
