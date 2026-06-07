from __future__ import annotations

import logging

from app.cache import CacheClient
from app.cache.redis_client import CacheUnavailableError
from app.circuit_breaker.breaker import CircuitDecision, CircuitState, run_circuit_action
from app.config.store import get_config_store
from app.exceptions.gateway import CircuitOpenError
from app.alerts.slack import SlackAlertService
from app.telemetry.metrics import record_circuit_state

logger = logging.getLogger(__name__)


class CircuitBreakerService:
    """Distributed per-provider circuit breaker backed by Redis."""

    def __init__(self, cache: CacheClient):
        self._cache = cache

    def allow_request(self, provider: str) -> CircuitDecision:
        config = get_config_store().get().resilience.circuit_breaker
        key = self._key(provider)
        try:
            decision = run_circuit_action(
                self._cache,
                key=key,
                threshold=config.failure_threshold,
                recovery_timeout=config.recovery_timeout_seconds,
                half_open_max=config.half_open_max_calls,
                action="check",
            )
        except CacheUnavailableError:
            logger.warning("Circuit breaker unavailable; allowing request provider=%s", provider)
            return CircuitDecision(allowed=True, state=CircuitState.CLOSED)

        if not decision.allowed:
            record_circuit_state(provider, decision.state.value)
            if decision.state == CircuitState.OPEN:
                SlackAlertService().circuit_open(provider=provider, state=decision.state.value)
            raise CircuitOpenError(provider, state=decision.state.value)
        record_circuit_state(provider, decision.state.value)
        return decision

    def record_success(self, provider: str) -> CircuitState:
        config = get_config_store().get().resilience.circuit_breaker
        try:
            decision = run_circuit_action(
                self._cache,
                key=self._key(provider),
                threshold=config.failure_threshold,
                recovery_timeout=config.recovery_timeout_seconds,
                half_open_max=config.half_open_max_calls,
                action="success",
            )
            record_circuit_state(provider, decision.state.value)
            return decision.state
        except CacheUnavailableError:
            logger.warning("Circuit breaker success record skipped provider=%s", provider)
            return CircuitState.CLOSED

    def record_failure(self, provider: str) -> CircuitState:
        config = get_config_store().get().resilience.circuit_breaker
        try:
            decision = run_circuit_action(
                self._cache,
                key=self._key(provider),
                threshold=config.failure_threshold,
                recovery_timeout=config.recovery_timeout_seconds,
                half_open_max=config.half_open_max_calls,
                action="failure",
            )
            record_circuit_state(provider, decision.state.value)
            if decision.state == CircuitState.OPEN:
                SlackAlertService().circuit_open(provider=provider, state=decision.state.value)
            return decision.state
        except CacheUnavailableError:
            logger.warning("Circuit breaker failure record skipped provider=%s", provider)
            return CircuitState.CLOSED

    def _key(self, provider: str) -> str:
        return f"cb:{provider.lower()}"
