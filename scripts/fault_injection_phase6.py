#!/usr/bin/env python3
"""Fault injection and recovery validation for Phase 6."""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx


def _chat(client: httpx.Client, url: str, api_key: str, model: str) -> tuple[int, str]:
    response = client.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "fault injection test"}],
        },
        timeout=30.0,
    )
    provider = ""
    if response.status_code == 200:
        provider = response.json().get("provider", "")
    return response.status_code, provider


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 fault injection test")
    parser.add_argument("--base-url", default=os.environ.get("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("GATEWAY_API_KEY", ""))
    parser.add_argument("--primary-model", default="gpt-4.1-mini")
    parser.add_argument("--fallback-model", default="mock-chat")
    args = parser.parse_args()

    if not args.api_key:
        print("Set GATEWAY_API_KEY or pass --api-key", file=sys.stderr)
        return 1

    base = args.base_url.rstrip("/")
    url = f"{base}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {args.api_key}"}

    with httpx.Client(timeout=30.0) as client:
        print("== Baseline health ==")
        health = client.get(f"{base}/health")
        print(f"Health status: {health.status_code}")
        for provider in health.json().get("providers", []):
            print(
                f"  {provider['provider']}: healthy={provider['healthy']} "
                f"circuit={provider.get('circuit_state', 'n/a')}"
            )

        print("\n== Primary route (may failover) ==")
        status, provider = _chat(client, url, args.api_key, args.primary_model)
        print(f"  status={status} provider={provider or 'n/a'}")

        print("\n== Mock provider (stable) ==")
        status, provider = _chat(client, url, args.api_key, args.fallback_model)
        print(f"  status={status} provider={provider or 'n/a'}")
        if status != 200:
            return 1

        print("\n== Recovery probe (3 requests) ==")
        recovered = 0
        for index in range(3):
            status, provider = _chat(client, url, args.api_key, args.fallback_model)
            print(f"  attempt {index + 1}: status={status} provider={provider}")
            if status == 200:
                recovered += 1
            time.sleep(0.5)

        print(f"\nRecovery: {recovered}/3 successful")
        return 0 if recovered == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
