from __future__ import annotations

from collections.abc import AsyncIterator

from app.providers.base import BaseProvider
from app.providers.factory import ProviderFactory
from app.providers.schemas import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateRequest,
    StreamChunk,
)
from app.schemas.gateway_response import GatewayResponse


class LLMService:
    """
    Application service that selects a provider and executes LLM calls.

    The API layer depends on this service only — never on OpenAI/Anthropic SDKs.
    Chat completions always return GatewayResponse.
    """

    def __init__(self, factory: type[ProviderFactory] = ProviderFactory):
        self._factory = factory

    def _provider(
        self,
        provider_name: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> BaseProvider:
        return self._factory.get_provider(
            provider_name,
            api_key=api_key,
            base_url=base_url,
        )

    async def generate(
        self,
        request: GenerateRequest,
        *,
        provider: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> GatewayResponse:
        return await self._provider(
            provider,
            api_key=api_key,
            base_url=base_url,
        ).generate(request)

    async def stream(
        self,
        request: GenerateRequest,
        *,
        provider: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        provider_impl = self._provider(
            provider,
            api_key=api_key,
            base_url=base_url,
        )
        async for chunk in provider_impl.stream(request):
            yield chunk

    async def embeddings(
        self,
        request: EmbeddingRequest,
        *,
        provider: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> EmbeddingResponse:
        return await self._provider(
            provider,
            api_key=api_key,
            base_url=base_url,
        ).embeddings(request)
