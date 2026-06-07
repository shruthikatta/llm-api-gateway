from __future__ import annotations

import json
import time
from dataclasses import dataclass

from app.cache import CacheClient
from app.cache.redis_client import CacheUnavailableError


@dataclass(slots=True, frozen=True)
class ProviderHealthSnapshot:
    provider: str
    healthy: bool
    latency_ms_ema: float
    error_rate: float
    consecutive_failures: int
    last_probe_at: float | None
    circuit_state: str | None = None


class ProviderHealthStore:
    """Rolling provider health metrics."""

    def __init__(self, cache: CacheClient, *, window_seconds: int = 60):
        self._cache = cache
        self._window = window_seconds
        self._local: dict[str, dict] = {}

    def record_outcome(
        self,
        provider: str,
        *,
        success: bool,
        latency_ms: float,
    ) -> None:
        stats = self._load(provider)
        stats["samples"] = int(stats.get("samples", 0)) + 1
        if success:
            stats["consecutive_failures"] = 0
        else:
            stats["errors"] = int(stats.get("errors", 0)) + 1
            stats["consecutive_failures"] = int(stats.get("consecutive_failures", 0)) + 1

        alpha = 2.0 / (self._window + 1.0)
        ema = float(stats.get("latency_ema", 0.0))
        stats["latency_ema"] = latency_ms if ema == 0 else ema * (1 - alpha) + latency_ms * alpha
        stats["last_probe_at"] = time.time()
        self._save(provider, stats)

    def get_snapshot(
        self,
        provider: str,
        *,
        circuit_state: str | None = None,
    ) -> ProviderHealthSnapshot:
        stats = self._load(provider)
        samples = max(1, int(stats.get("samples", 0)))
        errors = int(stats.get("errors", 0))
        error_rate = errors / samples
        consecutive = int(stats.get("consecutive_failures", 0))
        healthy = consecutive < 3 and error_rate < 0.5
        last_probe = stats.get("last_probe_at")
        return ProviderHealthSnapshot(
            provider=provider,
            healthy=healthy,
            latency_ms_ema=float(stats.get("latency_ema", 0.0)),
            error_rate=error_rate,
            consecutive_failures=consecutive,
            last_probe_at=float(last_probe) if last_probe else None,
            circuit_state=circuit_state,
        )

    def list_snapshots(self, providers: list[str]) -> list[ProviderHealthSnapshot]:
        return [self.get_snapshot(name) for name in providers]

    def _load(self, provider: str) -> dict:
        if provider in self._local:
            return dict(self._local[provider])

        key = self._key(provider)
        try:
            raw = self._cache.get(key)
            if raw:
                stats = json.loads(raw)
                self._local[provider] = stats
                return dict(stats)
        except CacheUnavailableError:
            pass

        return {
            "samples": 0,
            "errors": 0,
            "latency_ema": 0.0,
            "consecutive_failures": 0,
            "last_probe_at": 0,
        }

    def _save(self, provider: str, stats: dict) -> None:
        self._local[provider] = stats
        try:
            self._cache.set(
                self._key(provider),
                json.dumps(stats),
                ttl_seconds=self._window * 2,
            )
        except CacheUnavailableError:
            pass

    def _key(self, provider: str) -> str:
        return f"ph:{provider.lower()}"
