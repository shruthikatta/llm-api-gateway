from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from app.core.constants import DEFAULT_TIMEOUT_SECONDS
from app.exceptions.gateway import ProviderError, ValidationError
from app.exceptions.mapper import map_provider_exception
from app.providers.base import BaseProvider
from app.providers.http import AsyncHttpClient
from app.providers.http_errors import map_httpx_exception
from app.providers.schemas import (
    ChatMessage,
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateRequest,
    StreamChunk,
)
from app.schemas.gateway_response import (
    GatewayChoice,
    GatewayMessage,
    GatewayResponse,
    GatewayUsage,
)

PROVIDER_NAME = "anthropic"
DEFAULT_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


def _split_system(messages: list[ChatMessage]) -> tuple[str | None, list[dict[str, str]]]:
    system_parts: list[str] = []
    converted: list[dict[str, str]] = []
    for message in messages:
        if message.role == "system":
            system_parts.append(message.content)
            continue
        role = message.role if message.role in {"user", "assistant"} else "user"
        converted.append({"role": role, "content": message.content})
    system = "\n\n".join(system_parts) if system_parts else None
    return system, converted


def _to_anthropic_payload(request: GenerateRequest, *, stream: bool) -> dict[str, Any]:
    system, messages = _split_system(request.messages)
    if not messages:
        raise ValidationError("Anthropic requires at least one non-system message.")

    payload: dict[str, Any] = {
        "model": request.model,
        "messages": messages,
        "max_tokens": request.max_tokens or 1024,
        "temperature": request.temperature,
        "stream": stream,
    }
    if system:
        payload["system"] = system
    if request.top_p is not None:
        payload["top_p"] = request.top_p
    if request.stop is not None:
        payload["stop_sequences"] = request.stop
    return payload


def _normalize_response(data: dict[str, Any], *, latency_ms: float) -> GatewayResponse:
    content_blocks = data.get("content") or []
    text = "".join(
        block.get("text", "")
        for block in content_blocks
        if isinstance(block, dict) and block.get("type") == "text"
    )
    usage = data.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)

    return GatewayResponse(
        id=str(data.get("id") or ""),
        provider=PROVIDER_NAME,
        model=str(data.get("model") or ""),
        created=None,
        choices=[
            GatewayChoice(
                index=0,
                message=GatewayMessage(role="assistant", content=text),
                finish_reason=data.get("stop_reason"),
            )
        ],
        usage=GatewayUsage(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        latency_ms=latency_ms,
    )


class AnthropicProvider(BaseProvider):
    name = PROVIDER_NAME

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        base_url: str | None = None,
        http_client: AsyncHttpClient | None = None,
    ):
        self._api_key = api_key
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._http = http_client or AsyncHttpClient(
            timeout=timeout,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            base_url=self._base_url,
        )

    async def generate(self, request: GenerateRequest) -> GatewayResponse:
        started = time.perf_counter()
        payload = _to_anthropic_payload(request, stream=False)
        try:
            response = await self._http.post("/v1/messages", json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            mapped = map_httpx_exception(exc, provider=PROVIDER_NAME)
            raise map_provider_exception(
                mapped or exc,
                provider=PROVIDER_NAME,
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        return _normalize_response(data, latency_ms=latency_ms)

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamChunk]:
        payload = _to_anthropic_payload(request, stream=True)
        response_id = ""
        model = request.model
        try:
            async with self._http.stream(
                "POST",
                "/v1/messages",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    event = json.loads(raw)
                    event_type = event.get("type")
                    if event_type == "message_start":
                        message = event.get("message") or {}
                        response_id = str(message.get("id") or response_id)
                        model = str(message.get("model") or model)
                    elif event_type == "content_block_delta":
                        delta = event.get("delta") or {}
                        text = delta.get("text") or ""
                        if text:
                            yield StreamChunk(
                                id=response_id or "anthropic-stream",
                                model=model,
                                provider=PROVIDER_NAME,
                                delta=text,
                            )
                    elif event_type == "message_delta":
                        delta = event.get("delta") or {}
                        finish = delta.get("stop_reason")
                        if finish:
                            yield StreamChunk(
                                id=response_id or "anthropic-stream",
                                model=model,
                                provider=PROVIDER_NAME,
                                delta="",
                                finish_reason=finish,
                            )
        except Exception as exc:
            mapped = map_httpx_exception(exc, provider=PROVIDER_NAME)
            raise map_provider_exception(
                mapped or exc,
                provider=PROVIDER_NAME,
            ) from exc

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise ProviderError(
            "Anthropic embeddings are not supported by this gateway adapter.",
            provider=PROVIDER_NAME,
        )
