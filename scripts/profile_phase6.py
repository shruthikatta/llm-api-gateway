#!/usr/bin/env python3
"""Memory and CPU profiling wrapper for gateway benchmarks."""

from __future__ import annotations

import argparse
import cProfile
import pstats
import subprocess
import sys
import tracemalloc


def _run_benchmark(args: argparse.Namespace) -> None:
    cmd = [
        sys.executable,
        "scripts/benchmark_phase6.py",
        "--requests",
        str(args.requests),
        "--concurrency",
        str(args.concurrency),
    ]
    if args.api_key:
        cmd.extend(["--api-key", args.api_key])
    if args.base_url:
        cmd.extend(["--base-url", args.base_url])
    if args.stream:
        cmd.append("--stream")
    subprocess.run(cmd, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 profiling wrapper")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--cpu", action="store_true", help="Run cProfile CPU profile")
    parser.add_argument("--memory", action="store_true", help="Run tracemalloc memory profile")
    args = parser.parse_args()

    if not args.cpu and not args.memory:
        args.cpu = True
        args.memory = True

    if args.memory:
        tracemalloc.start()
        _run_benchmark(args)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(f"\nMemory current: {current / 1024 / 1024:.2f} MiB")
        print(f"Memory peak:    {peak / 1024 / 1024:.2f} MiB")
        return 0

    if args.cpu:
        profiler = cProfile.Profile()
        profiler.enable()
        _run_benchmark(args)
        profiler.disable()
        stats = pstats.Stats(profiler).sort_stats("cumulative")
        stats.print_stats(20)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
