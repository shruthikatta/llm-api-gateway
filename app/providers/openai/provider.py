from __future__ import annotations

import time
from collections.abc import AsyncIterator

from app.core.constants import DEFAULT_TIMEOUT_SECONDS
from app.exceptions.mapper import map_provider_exception
from app.providers.base import BaseProvider
from app.providers.openai.client import OpenAIClient
from app.providers.openai.mapper import (
    OpenAIMapper,
    from_openai_embedding_response,
    from_openai_stream_chunk,
    to_openai_chat_kwargs,
    to_openai_embedding_kwargs,
)
from app.providers.schemas import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateRequest,
    StreamChunk,
)
from app.schemas.gateway_response import GatewayResponse


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        base_url: str | None = None,
        client: OpenAIClient | None = None,
        mapper: OpenAIMapper | None = None,
    ):
        self._client = client or OpenAIClient(
            api_key=api_key,
            timeout=timeout,
            base_url=base_url,
        )
        self._mapper = mapper or OpenAIMapper()

    async def generate(self, request: GenerateRequest) -> GatewayResponse:
        started = time.perf_counter()
        try:
            response = await self._client.chat(**to_openai_chat_kwargs(request))
        except Exception as exc:
            raise map_provider_exception(exc, provider=self.name) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        return self._mapper.normalize_response(response, latency_ms=latency_ms)

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamChunk]:
        try:
            async for chunk in self._client.stream_chat(**to_openai_chat_kwargs(request)):
                mapped = from_openai_stream_chunk(chunk)
                if mapped is not None:
                    yield mapped
        except Exception as exc:
            raise map_provider_exception(exc, provider=self.name) from exc

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        started = time.perf_counter()
        try:
            response = await self._client.embeddings(
                **to_openai_embedding_kwargs(request)
            )
        except Exception as exc:
            raise map_provider_exception(exc, provider=self.name) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        return from_openai_embedding_response(response, latency_ms=latency_ms)

    async def health_check(self) -> bool:
        try:
            await self._client.models()
            return True
        except Exception:
            return False
