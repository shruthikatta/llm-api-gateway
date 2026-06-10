from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.cache.memory import MemoryCacheClient
from app.circuit_breaker.breaker import CircuitState, run_circuit_action
from app.circuit_breaker.service import CircuitBreakerService
from app.config.store import get_config_store
from app.exceptions.gateway import CircuitOpenError, ProviderError, TimeoutError
from app.providers.mock.provider import MockProvider
from app.retry.executor import RetryExecutor
from app.retry.policy import RetryPolicy


def test_circuit_breaker_opens_after_failures():
    cache = MemoryCacheClient()
    key = "cb:test"
    config = get_config_store().get().resilience.circuit_breaker

    for _ in range(config.failure_threshold):
        run_circuit_action(
            cache,
            key=key,
            threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout_seconds,
            half_open_max=config.half_open_max_calls,
            action="failure",
        )

    decision = run_circuit_action(
        cache,
        key=key,
        threshold=config.failure_threshold,
        recovery_timeout=config.recovery_timeout_seconds,
        half_open_max=config.half_open_max_calls,
        action="check",
    )
    assert decision.allowed is False
    assert decision.state == CircuitState.OPEN


def test_circuit_breaker_service_blocks_open_provider():
    cache = MemoryCacheClient()
    service = CircuitBreakerService(cache)
    provider = "mock"

    config = get_config_store().get().resilience.circuit_breaker
    for _ in range(config.failure_threshold):
        service.record_failure(provider)

    with pytest.raises(CircuitOpenError):
        service.allow_request(provider)


@pytest.mark.asyncio
async def test_retry_executor_retries_retryable_errors():
    calls = {"count": 0}

    async def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise TimeoutError("temporary", provider="mock")
        return "ok"

    policy = RetryPolicy(
        max_retries=3,
        base_delay_ms=1,
        max_delay_ms=5,
        retry_budget=3,
    )
    result = await RetryExecutor(policy).run(flaky, label="test")
    assert result == "ok"
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_retry_executor_does_not_retry_non_retryable():
    from app.exceptions.gateway import ValidationError

    async def fail() -> None:
        raise ValidationError("hard fail")

    policy = RetryPolicy(max_retries=3, base_delay_ms=1, max_delay_ms=5, retry_budget=3)
    with pytest.raises(ValidationError):
        await RetryExecutor(policy).run(fail, label="test")


@pytest.mark.asyncio
async def test_mock_provider_chaos_always_fail():
    provider = MockProvider(chaos_always_fail=True)
    from app.providers.schemas import ChatMessage, GenerateRequest

    request = GenerateRequest(
        model="mock-chat",
        messages=[ChatMessage(role="user", content="hello")],
    )
    with pytest.raises(ProviderError):
        await provider.generate(request)


def test_mock_provider_health_reflects_chaos():
    healthy = MockProvider(chaos_fail_rate=0.0)
    unhealthy = MockProvider(chaos_always_fail=True)
    assert asyncio.run(healthy.health_check()) is True
    assert asyncio.run(unhealthy.health_check()) is False
