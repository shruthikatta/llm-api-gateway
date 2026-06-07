from __future__ import annotations

import logging
import time

from app.cache import CacheClient
from app.circuit_breaker.service import CircuitBreakerService
from app.config.store import get_config_store
from app.health.store import ProviderHealthStore
from app.providers.factory import ProviderFactory
from app.providers.registry import PROVIDER_REGISTRY
from app.alerts.slack import SlackAlertService
from app.telemetry.metrics import PROVIDER_ERROR_RATE, PROVIDER_LATENCY_EMA_MS, record_circuit_state

logger = logging.getLogger(__name__)


class ProviderHealthService:
    def __init__(self, cache: CacheClient):
        window = get_config_store().get().resilience.circuit_breaker.rolling_window_seconds
        self._store = ProviderHealthStore(cache, window_seconds=window)
        self._breakers = CircuitBreakerService(cache)

    @property
    def store(self) -> ProviderHealthStore:
        return self._store

    async def probe_provider(self, provider_name: str) -> bool:
        if provider_name not in PROVIDER_REGISTRY:
            return False

        config = get_config_store().get()
        if not config.provider_enabled(provider_name):
            return False

        started = time.perf_counter()
        success = False
        try:
            provider = ProviderFactory.get_provider(provider_name)
            success = await provider.health_check()
        except Exception:
            logger.warning("Health probe failed provider=%s", provider_name, exc_info=True)
            success = False

        latency_ms = (time.perf_counter() - started) * 1000
        self._store.record_outcome(provider_name, success=success, latency_ms=latency_ms)
        snapshot = self._store.get_snapshot(provider_name)
        PROVIDER_LATENCY_EMA_MS.labels(provider=provider_name).set(snapshot.latency_ms_ema)
        PROVIDER_ERROR_RATE.labels(provider=provider_name).set(snapshot.error_rate)
        if snapshot.error_rate >= get_config_store().get().alerting.error_rate_threshold:
            SlackAlertService().high_error_rate(
                provider=provider_name,
                error_rate=snapshot.error_rate,
            )
        if success:
            state = self._breakers.record_success(provider_name)
        else:
            state = self._breakers.record_failure(provider_name)
        record_circuit_state(provider_name, state.value)
        return success

    async def probe_all_enabled(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name in PROVIDER_REGISTRY:
            if get_config_store().get().provider_enabled(name):
                results[name] = await self.probe_provider(name)
        return results
