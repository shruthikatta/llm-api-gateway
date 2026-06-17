#!/usr/bin/env python3
"""Phase 6 high-concurrency load test (5000+ requests via asyncio)."""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time

import httpx


async def _one_request(
    client: httpx.AsyncClient,
    *,
    url: str,
    api_key: str,
    semaphore: asyncio.Semaphore,
) -> tuple[int, float]:
    async with semaphore:
        started = time.perf_counter()
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "mock-chat",
                "messages": [{"role": "user", "content": "phase6 load"}],
            },
        )
        return response.status_code, (time.perf_counter() - started) * 1000


async def _run(args: argparse.Namespace) -> dict[str, object]:
    url = f"{args.base_url.rstrip('/')}/v1/chat/completions"
    semaphore = asyncio.Semaphore(args.concurrency)
    limits = httpx.Limits(
        max_connections=args.concurrency + 50,
        max_keepalive_connections=args.concurrency,
    )
    timeout = httpx.Timeout(args.timeout)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        started = time.perf_counter()
        results = await asyncio.gather(
            *[
                _one_request(client, url=url, api_key=args.api_key, semaphore=semaphore)
                for _ in range(args.requests)
            ],
            return_exceptions=True,
        )
        elapsed = time.perf_counter() - started

    statuses: list[int] = []
    latencies: list[float] = []
    errors = 0
    for result in results:
        if isinstance(result, Exception):
            errors += 1
            continue
        status, latency_ms = result
        statuses.append(status)
        latencies.append(latency_ms)

    return {
        "elapsed": elapsed,
        "statuses": statuses,
        "latencies": latencies,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 asyncio load test")
    parser.add_argument("--base-url", default=os.environ.get("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("GATEWAY_API_KEY", ""))
    parser.add_argument("--requests", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    if not args.api_key:
        print("Set GATEWAY_API_KEY or pass --api-key", file=sys.stderr)
        return 1

    summary = asyncio.run(_run(args))
    statuses = summary["statuses"]
    latencies = summary["latencies"]
    elapsed = float(summary["elapsed"])
    errors = int(summary["errors"])

    success = sum(1 for code in statuses if code == 200)
    rate_limited = sum(1 for code in statuses if code == 429)
    budget_blocked = sum(1 for code in statuses if code == 402)

    print(f"Completed {args.requests} requests in {elapsed:.2f}s")
    print(f"  concurrency:   {args.concurrency}")
    print(f"  200 OK:        {success}")
    print(f"  429 limited:   {rate_limited}")
    print(f"  402 budget:    {budget_blocked}")
    print(f"  exceptions:    {errors}")
    print(f"  other:         {len(statuses) - success - rate_limited - budget_blocked}")
    print(f"  throughput:    {args.requests / elapsed:.1f} req/s")
    if latencies:
        print(f"  latency p50:   {statistics.median(latencies):.1f} ms")
        print(f"  latency p95:   {sorted(latencies)[int(len(latencies) * 0.95) - 1]:.1f} ms")
    return 0 if success > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
