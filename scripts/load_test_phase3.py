#!/usr/bin/env python3
"""Lightweight concurrent load test for Phase 3 rate limiting."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import sys
import time

import httpx


def _request(client: httpx.Client, url: str, api_key: str) -> int:
    response = client.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "mock-chat",
            "messages": [{"role": "user", "content": "load test"}],
        },
        timeout=30.0,
    )
    return response.status_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 gateway load test")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GATEWAY_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GATEWAY_API_KEY", ""),
        help="Seeded development API key",
    )
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()

    if not args.api_key:
        print("Set GATEWAY_API_KEY or pass --api-key", file=sys.stderr)
        return 1

    url = f"{args.base_url.rstrip('/')}/v1/chat/completions"
    started = time.perf_counter()

    with httpx.Client() as client:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            statuses = list(
                pool.map(
                    lambda _: _request(client, url, args.api_key),
                    range(args.requests),
                )
            )

    elapsed = time.perf_counter() - started
    success = sum(1 for code in statuses if code == 200)
    rate_limited = sum(1 for code in statuses if code == 429)
    budget_blocked = sum(1 for code in statuses if code == 402)

    print(f"Completed {args.requests} requests in {elapsed:.2f}s")
    print(f"  200 OK:        {success}")
    print(f"  429 limited:   {rate_limited}")
    print(f"  402 budget:    {budget_blocked}")
    print(f"  other:         {args.requests - success - rate_limited - budget_blocked}")
    print(f"  throughput:    {args.requests / elapsed:.1f} req/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
