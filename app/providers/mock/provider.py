from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import AsyncIterator

from app.exceptions.gateway import ProviderError, TimeoutError, ValidationError
from app.providers.base import BaseProvider
from app.providers.schemas import (
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateRequest,
    StreamChunk,
    UsageInfo,
)
from app.schemas.gateway_response import (
    GatewayChoice,
    GatewayMessage,
    GatewayResponse,
    GatewayUsage,
)

PROVIDER_NAME = "mock"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _join_prompt(request: GenerateRequest) -> str:
    return "\n".join(message.content for message in request.messages)


def _build_reply(request: GenerateRequest) -> str:
    last_user = next(
        (m.content for m in reversed(request.messages) if m.role == "user"),
        "",
    )
    if last_user:
        return f"mock-response: {last_user}"
    return "mock-response: ok"


class MockProvider(BaseProvider):
    """
    Deterministic in-process provider for local development, tests, and chaos simulation.
    """

    name = PROVIDER_NAME

    def __init__(
        self,
        *,
        simulated_latency_ms: float = 5.0,
        chaos_fail_rate: float = 0.0,
        chaos_always_fail: bool = False,
    ):
        self._latency_ms = max(0.0, simulated_latency_ms)
        self._chaos_fail_rate = max(0.0, min(1.0, chaos_fail_rate))
        self._chaos_always_fail = chaos_always_fail

    async def health_check(self) -> bool:
        if self._chaos_always_fail:
            return False
        return random.random() >= self._chaos_fail_rate

    async def generate(self, request: GenerateRequest) -> GatewayResponse:
        self._maybe_fail()
        started = time.perf_counter()
        if self._latency_ms:
            await asyncio.sleep(self._latency_ms / 1000)

        reply = _build_reply(request)
        prompt_tokens = _estimate_tokens(_join_prompt(request))
        completion_tokens = _estimate_tokens(reply)
        latency_ms = (time.perf_counter() - started) * 1000

        return GatewayResponse(
            id=f"mock-{uuid.uuid4().hex}",
            provider=PROVIDER_NAME,
            model=request.model,
            created=int(time.time()),
            choices=[
                GatewayChoice(
                    index=0,
                    message=GatewayMessage(role="assistant", content=reply),
                    finish_reason="stop",
                )
            ],
            usage=GatewayUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            latency_ms=latency_ms,
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamChunk]:
        self._maybe_fail()
        reply = _build_reply(request)
        response_id = f"mock-{uuid.uuid4().hex}"
        words = reply.split(" ")
        for index, word in enumerate(words):
            if self._latency_ms:
                await asyncio.sleep(self._latency_ms / 1000)
            delta = word if index == 0 else f" {word}"
            yield StreamChunk(
                id=response_id,
                model=request.model,
                provider=PROVIDER_NAME,
                delta=delta,
                finish_reason=None,
            )
        yield StreamChunk(
            id=response_id,
            model=request.model,
            provider=PROVIDER_NAME,
            delta="",
            finish_reason="stop",
        )

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self._maybe_fail()
        started = time.perf_counter()
        if self._latency_ms:
            await asyncio.sleep(self._latency_ms / 1000)

        inputs = request.input if isinstance(request.input, list) else [request.input]
        if not inputs:
            raise ValidationError("Embedding input must not be empty.")

        dimensions = request.dimensions or 8
        data = [
            EmbeddingData(
                index=index,
                embedding=[
                    float((index + 1) * (offset + 1)) for offset in range(dimensions)
                ],
            )
            for index, _ in enumerate(inputs)
        ]
        prompt_tokens = sum(_estimate_tokens(item) for item in inputs)
        latency_ms = (time.perf_counter() - started) * 1000

        return EmbeddingResponse(
            id=f"mock-emb-{uuid.uuid4().hex}",
            model=request.model,
            provider=PROVIDER_NAME,
            data=data,
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                total_tokens=prompt_tokens,
            ),
            latency_ms=latency_ms,
        )

    def _maybe_fail(self) -> None:
        if self._chaos_always_fail:
            raise ProviderError("Mock provider configured to always fail.", provider=PROVIDER_NAME)
        if self._chaos_fail_rate and random.random() < self._chaos_fail_rate:
            raise TimeoutError("Mock provider simulated timeout.", provider=PROVIDER_NAME)
