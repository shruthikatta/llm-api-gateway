#!/usr/bin/env python3
"""Latency and throughput benchmark for Phase 6."""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time

import httpx


async def _benchmark(
    *,
    base_url: str,
    api_key: str,
    requests: int,
    concurrency: int,
    stream: bool,
) -> dict[str, float | int]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    statuses: list[int] = []

    async def _one(client: httpx.AsyncClient) -> None:
        async with semaphore:
            started = time.perf_counter()
            if stream:
                async with client.stream(
                    "POST",
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "mock-chat",
                        "stream": True,
                        "messages": [{"role": "user", "content": "benchmark"}],
                    },
                ) as response:
                    statuses.append(response.status_code)
                    async for _ in response.aiter_lines():
                        pass
            else:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "mock-chat",
                        "messages": [{"role": "user", "content": "benchmark"}],
                    },
                )
                statuses.append(response.status_code)
            latencies.append((time.perf_counter() - started) * 1000)

    limits = httpx.Limits(max_connections=concurrency + 20)
    started = time.perf_counter()
    async with httpx.AsyncClient(limits=limits, timeout=60.0) as client:
        await asyncio.gather(*[_one(client) for _ in range(requests)])
    elapsed = time.perf_counter() - started

    sorted_latencies = sorted(latencies)
    return {
        "elapsed_s": elapsed,
        "requests": requests,
        "success": sum(1 for code in statuses if code == 200),
        "throughput_rps": requests / elapsed,
        "p50_ms": statistics.median(sorted_latencies),
        "p95_ms": sorted_latencies[int(len(sorted_latencies) * 0.95) - 1],
        "p99_ms": sorted_latencies[int(len(sorted_latencies) * 0.99) - 1],
        "max_ms": sorted_latencies[-1],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 benchmark")
    parser.add_argument("--base-url", default=os.environ.get("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("GATEWAY_API_KEY", ""))
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()

    if not args.api_key:
        print("Set GATEWAY_API_KEY or pass --api-key", file=sys.stderr)
        return 1

    result = asyncio.run(
        _benchmark(
            base_url=args.base_url,
            api_key=args.api_key,
            requests=args.requests,
            concurrency=args.concurrency,
            stream=args.stream,
        )
    )

    mode = "streaming" if args.stream else "non-streaming"
    print(f"Benchmark ({mode})")
    for key, value in result.items():
        if key.endswith("_ms"):
            print(f"  {key}: {value:.1f}")
        elif key == "throughput_rps":
            print(f"  {key}: {value:.1f}")
        else:
            print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
