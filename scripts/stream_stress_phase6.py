#!/usr/bin/env python3
"""Streaming stress test — concurrent SSE connections."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

import httpx


async def _stream_once(
    client: httpx.AsyncClient,
    *,
    url: str,
    api_key: str,
    semaphore: asyncio.Semaphore,
) -> tuple[int, int, float]:
    async with semaphore:
        started = time.perf_counter()
        chunks = 0
        async with client.stream(
            "POST",
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "mock-chat",
                "stream": True,
                "messages": [{"role": "user", "content": "stream stress"}],
            },
        ) as response:
            status = response.status_code
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    chunks += 1
        return status, chunks, (time.perf_counter() - started) * 1000


async def _run(args: argparse.Namespace) -> list[tuple[int, int, float]]:
    url = f"{args.base_url.rstrip('/')}/v1/chat/completions"
    semaphore = asyncio.Semaphore(args.concurrency)
    limits = httpx.Limits(max_connections=args.concurrency + 20)

    async with httpx.AsyncClient(limits=limits, timeout=args.timeout) as client:
        return await asyncio.gather(
            *[
                _stream_once(client, url=url, api_key=args.api_key, semaphore=semaphore)
                for _ in range(args.streams)
            ]
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 streaming stress test")
    parser.add_argument("--base-url", default=os.environ.get("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("GATEWAY_API_KEY", ""))
    parser.add_argument("--streams", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    if not args.api_key:
        print("Set GATEWAY_API_KEY or pass --api-key", file=sys.stderr)
        return 1

    started = time.perf_counter()
    results = asyncio.run(_run(args))
    elapsed = time.perf_counter() - started

    ok = sum(1 for status, _, _ in results if status == 200)
    total_chunks = sum(chunks for _, chunks, _ in results)
    print(f"Completed {args.streams} streams in {elapsed:.2f}s")
    print(f"  200 OK:      {ok}")
    print(f"  SSE chunks:  {total_chunks}")
    print(f"  throughput:  {args.streams / elapsed:.1f} streams/s")
    return 0 if ok == args.streams else 1


if __name__ == "__main__":
    raise SystemExit(main())
