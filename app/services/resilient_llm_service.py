from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

from app.cache import CacheClient
from app.circuit_breaker.service import CircuitBreakerService
from app.config.store import get_config_store
from app.exceptions.base import GatewayError
from app.health.store import ProviderHealthStore
from app.providers.schemas import GenerateRequest, StreamChunk
from app.retry.executor import RetryExecutor
from app.schemas.gateway_response import GatewayResponse
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ResilientLLMService:
    """Wraps LLMService with circuit breaking, retries, timeouts, and health tracking."""

    def __init__(
        self,
        cache: CacheClient,
        llm_service: LLMService | None = None,
    ):
        self._llm = llm_service or LLMService()
        self._breakers = CircuitBreakerService(cache)
        window = get_config_store().get().resilience.circuit_breaker.rolling_window_seconds
        self._health = ProviderHealthStore(cache, window_seconds=window)
        self._retry = RetryExecutor()

    async def generate(
        self,
        request: GenerateRequest,
        *,
        provider: str,
        base_url: str | None = None,
        retry_budget: int | None = None,
    ) -> GatewayResponse:
        self._breakers.allow_request(provider)
        started = time.perf_counter()
        timeout = get_config_store().get().resilience.request_timeout_seconds

        async def _call() -> GatewayResponse:
            return await asyncio.wait_for(
                self._llm.generate(request, provider=provider, base_url=base_url),
                timeout=timeout,
            )

        try:
            response = await self._retry.run(
                _call,
                label=f"generate:{provider}",
                budget=retry_budget,
            )
            self._record_success(provider, started)
            return response
        except GatewayError:
            self._record_failure(provider, started)
            raise
        except Exception as exc:
            self._record_failure(provider, started)
            raise GatewayError(str(exc)) from exc

    async def stream(
        self,
        request: GenerateRequest,
        *,
        provider: str,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        self._breakers.allow_request(provider)
        started = time.perf_counter()
        timeout = get_config_store().get().resilience.request_timeout_seconds

        try:
            async with asyncio.timeout(timeout):
                async for chunk in self._llm.stream(
                    request,
                    provider=provider,
                    base_url=base_url,
                ):
                    yield chunk
            self._record_success(provider, started)
        except GatewayError:
            self._record_failure(provider, started)
            raise
        except Exception as exc:
            self._record_failure(provider, started)
            raise GatewayError(str(exc)) from exc

    def _record_success(self, provider: str, started: float) -> None:
        latency_ms = (time.perf_counter() - started) * 1000
        self._breakers.record_success(provider)
        self._health.record_outcome(provider, success=True, latency_ms=latency_ms)

    def _record_failure(self, provider: str, started: float) -> None:
        latency_ms = (time.perf_counter() - started) * 1000
        self._breakers.record_failure(provider)
        self._health.record_outcome(provider, success=False, latency_ms=latency_ms)
