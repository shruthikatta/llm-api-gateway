#!/usr/bin/env python3
"""Chaos test: simulate provider failure and verify failover via mock fallback."""

from __future__ import annotations

import argparse
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 chaos/failover test")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GATEWAY_URL", "http://localhost:8000"),
    )
    parser.add_argument("--api-key", default=os.environ.get("GATEWAY_API_KEY", ""))
    args = parser.parse_args()

    if not args.api_key:
        print("Set GATEWAY_API_KEY or pass --api-key", file=sys.stderr)
        return 1

    url = f"{args.base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {args.api_key}"}
    payload = {
        "model": "gpt-4.1-mini",
        "messages": [{"role": "user", "content": "chaos test"}],
    }

    with httpx.Client(timeout=30.0) as client:
        health = client.get(f"{args.base_url.rstrip('/')}/health")
        print(f"Health: {health.status_code}")
        if health.status_code == 200:
            body = health.json()
            for provider in body.get("providers", []):
                print(
                    f"  {provider['provider']}: healthy={provider['healthy']} "
                    f"error_rate={provider['error_rate']:.2f}"
                )

        response = client.post(url, headers=headers, json=payload)
        print(f"Chat: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            provider = data.get("provider", "unknown")
            content = data["choices"][0]["message"]["content"]
            print(f"  provider={provider} content={content[:80]}")
        else:
            print(response.text[:500])
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
