from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from app.providers.schemas import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateRequest,
    StreamChunk,
)
from app.schemas.gateway_response import GatewayResponse


class ProviderMapper(ABC):
    """
    Convert a vendor SDK response into the gateway's normalized schema.
    """

    @abstractmethod
    def normalize_response(
        self,
        response: Any,
        latency_ms: float,
    ) -> GatewayResponse:
        """Map a provider-native response to GatewayResponse."""


class BaseProvider(ABC):
    """
    Provider-agnostic LLM interface.

    Implementations must not depend on FastAPI, auth, or the database.
    Chat completions always return GatewayResponse.
    """

    name: str

    @abstractmethod
    async def generate(self, request: GenerateRequest) -> GatewayResponse:
        """Non-streaming chat completion."""

    @abstractmethod
    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamChunk]:
        """Streaming chat completion as an async iterator of chunks."""

    @abstractmethod
    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Create embeddings for the given input."""

    async def health_check(self) -> bool:
        """Lightweight probe used by background health workers."""
        return True
