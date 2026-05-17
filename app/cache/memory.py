from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field


@dataclass
class _BucketState:
    tokens: float
    last_refill: float


@dataclass
class _CounterState:
    value: float = 0.0


@dataclass
class _CircuitState:
    state: str = "closed"
    failures: int = 0
    opened_at: float = 0.0
    half_open_calls: int = 0


@dataclass
class MemoryCacheClient:
    """In-process cache for unit tests."""

    _buckets: dict[str, _BucketState] = field(default_factory=dict)
    _counters: dict[str, _CounterState] = field(default_factory=dict)
    _circuits: dict[str, _CircuitState] = field(default_factory=dict)
    _strings: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _available: bool = True

    def ping(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    def eval_script(
        self,
        script: str,
        keys: list[str],
        args: list[str],
    ) -> list[int | float | str] | int | float | str | None:
        if not self._available:
            from app.cache.redis_client import CacheUnavailableError

            raise CacheUnavailableError("Cache backend unavailable.")

        if "HMGET" in script and "tokens" in script:
            return self._token_bucket(keys[0], args)
        if "INCRBYFLOAT" in script:
            return self._budget_check(keys[0], args)
        if "HGET" in script and "state" in script:
            return self._circuit_breaker(keys[0], args)
        raise NotImplementedError(f"Unsupported script in MemoryCacheClient: {script[:40]}")

    def _token_bucket(self, key: str, args: list[str]) -> list[int | float]:
        capacity = float(args[0])
        refill_rate = float(args[1])
        now = float(args[2])
        requested = float(args[3])

        with self._lock:
            state = self._buckets.get(key)
            if state is None:
                state = _BucketState(tokens=capacity, last_refill=now)
                self._buckets[key] = state

            elapsed = max(0.0, now - state.last_refill)
            state.tokens = min(capacity, state.tokens + elapsed * refill_rate)
            state.last_refill = now

            if requested > 0 and state.tokens < requested:
                deficit = requested - state.tokens
                retry_after = int(deficit / refill_rate) + 1 if refill_rate > 0 else 60
                return [0, retry_after, state.tokens]

            if requested < 0:
                state.tokens = min(capacity, state.tokens - requested)
            else:
                state.tokens -= requested
            return [1, 0, state.tokens]

    def _budget_check(self, key: str, args: list[str]) -> list[int | float]:
        limit = float(args[0])
        amount = float(args[1])

        with self._lock:
            counter = self._counters.setdefault(key, _CounterState())
            if amount > 0 and counter.value + amount > limit:
                return [0, counter.value]
            counter.value += amount
            return [1, counter.value]

    def _circuit_breaker(self, key: str, args: list[str]) -> list[int | str]:
        threshold = int(args[0])
        recovery_timeout = float(args[1])
        half_open_max = int(args[2])
        now = float(args[3])
        action = args[4]

        with self._lock:
            cb = self._circuits.setdefault(key, _CircuitState())

            if action == "check":
                if cb.state == "open":
                    if now - cb.opened_at >= recovery_timeout:
                        cb.state = "half_open"
                        cb.half_open_calls = 0
                    else:
                        return [0, cb.state]
                if cb.state == "half_open":
                    if cb.half_open_calls >= half_open_max:
                        return [0, cb.state]
                    cb.half_open_calls += 1
                return [1, cb.state]

            if action == "success":
                cb.state = "closed"
                cb.failures = 0
                cb.half_open_calls = 0
                return [1, "closed"]

            if action == "failure":
                cb.failures += 1
                if cb.state == "half_open" or cb.failures >= threshold:
                    cb.state = "open"
                    cb.opened_at = now
                    cb.failures = 0
                    cb.half_open_calls = 0
                    return [0, "open"]
                return [1, cb.state]

            return [0, cb.state]

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._strings.get(key)

    def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        with self._lock:
            self._strings[key] = value

    def close(self) -> None:
        return None
