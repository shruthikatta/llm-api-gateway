from __future__ import annotations

from typing import Any

from app.providers.base import ProviderMapper
from app.providers.schemas import (
    ChatMessage,
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

PROVIDER_NAME = "openai"


class OpenAIMapper(ProviderMapper):
    """Maps OpenAI SDK objects into gateway-normalized schemas."""

    def normalize_response(
        self,
        response: Any,
        latency_ms: float,
    ) -> GatewayResponse:
        usage = response.usage

        return GatewayResponse(
            id=response.id,
            provider=PROVIDER_NAME,
            model=response.model,
            created=getattr(response, "created", None),
            choices=[
                GatewayChoice(
                    index=index,
                    message=GatewayMessage(
                        role=getattr(choice.message, "role", None) or "assistant",
                        content=choice.message.content or "",
                    ),
                    finish_reason=choice.finish_reason,
                )
                for index, choice in enumerate(response.choices)
            ],
            usage=GatewayUsage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(usage, "total_tokens", 0) or 0,
            ),
            latency_ms=latency_ms,
        )


def to_openai_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def to_openai_chat_kwargs(request: GenerateRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": to_openai_messages(request.messages),
        "temperature": request.temperature,
    }
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.top_p is not None:
        payload["top_p"] = request.top_p
    if request.stop is not None:
        payload["stop"] = request.stop
    return payload


def to_openai_embedding_kwargs(request: EmbeddingRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": request.model,
        "input": request.input,
    }
    if request.dimensions is not None:
        payload["dimensions"] = request.dimensions
    return payload


def from_openai_stream_chunk(chunk: Any) -> StreamChunk | None:
    if not chunk.choices:
        return None

    choice = chunk.choices[0]
    delta = choice.delta.content or ""
    finish_reason = choice.finish_reason

    if not delta and finish_reason is None:
        return None

    return StreamChunk(
        id=chunk.id,
        model=chunk.model,
        provider=PROVIDER_NAME,
        delta=delta,
        finish_reason=finish_reason,
    )


def from_openai_embedding_response(
    response: Any,
    *,
    latency_ms: float,
) -> EmbeddingResponse:
    usage = response.usage
    data = [
        EmbeddingData(index=item.index, embedding=list(item.embedding))
        for item in response.data
    ]

    return EmbeddingResponse(
        id=getattr(response, "id", "") or "",
        model=response.model,
        provider=PROVIDER_NAME,
        data=data,
        usage=UsageInfo(
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        ),
        latency_ms=latency_ms,
        raw=response.model_dump() if hasattr(response, "model_dump") else None,
    )
