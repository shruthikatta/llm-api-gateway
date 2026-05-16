from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from app.core.constants import DEFAULT_TIMEOUT_SECONDS
from app.exceptions.mapper import map_provider_exception
from app.providers.base import BaseProvider
from app.providers.http import AsyncHttpClient
from app.providers.http_errors import map_httpx_exception
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

PROVIDER_NAME = "ollama"
DEFAULT_BASE_URL = "http://localhost:11434"


def _to_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _chat_payload(request: GenerateRequest, *, stream: bool) -> dict[str, Any]:
    options: dict[str, Any] = {"temperature": request.temperature}
    if request.top_p is not None:
        options["top_p"] = request.top_p
    if request.stop is not None:
        options["stop"] = request.stop
    if request.max_tokens is not None:
        options["num_predict"] = request.max_tokens

    return {
        "model": request.model,
        "messages": _to_messages(request.messages),
        "stream": stream,
        "options": options,
    }


def _normalize_chat(data: dict[str, Any], *, latency_ms: float) -> GatewayResponse:
    message = data.get("message") or {}
    prompt_tokens = int(data.get("prompt_eval_count") or 0)
    completion_tokens = int(data.get("eval_count") or 0)

    return GatewayResponse(
        id=f"ollama-{data.get('created_at', '')}",
        provider=PROVIDER_NAME,
        model=str(data.get("model") or ""),
        created=None,
        choices=[
            GatewayChoice(
                index=0,
                message=GatewayMessage(
                    role=str(message.get("role") or "assistant"),
                    content=str(message.get("content") or ""),
                ),
                finish_reason="stop" if data.get("done") else None,
            )
        ],
        usage=GatewayUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
        latency_ms=latency_ms,
    )


class OllamaProvider(BaseProvider):
    name = PROVIDER_NAME

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        base_url: str | None = None,
        api_key: str | None = None,
        http_client: AsyncHttpClient | None = None,
    ):
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        headers = {"content-type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = http_client or AsyncHttpClient(
            timeout=timeout,
            headers=headers,
            base_url=self._base_url,
        )

    async def generate(self, request: GenerateRequest) -> GatewayResponse:
        started = time.perf_counter()
        payload = _chat_payload(request, stream=False)
        try:
            response = await self._http.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            mapped = map_httpx_exception(exc, provider=PROVIDER_NAME)
            raise map_provider_exception(
                mapped or exc,
                provider=PROVIDER_NAME,
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        return _normalize_chat(data, latency_ms=latency_ms)

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamChunk]:
        payload = _chat_payload(request, stream=True)
        response_id = f"ollama-{int(time.time())}"
        try:
            async with self._http.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message") or {}
                    delta = str(message.get("content") or "")
                    done = bool(data.get("done"))
                    if delta or done:
                        yield StreamChunk(
                            id=response_id,
                            model=str(data.get("model") or request.model),
                            provider=PROVIDER_NAME,
                            delta=delta,
                            finish_reason="stop" if done else None,
                        )
        except Exception as exc:
            mapped = map_httpx_exception(exc, provider=PROVIDER_NAME)
            raise map_provider_exception(
                mapped or exc,
                provider=PROVIDER_NAME,
            ) from exc

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        started = time.perf_counter()
        inputs = request.input if isinstance(request.input, list) else [request.input]
        data: list[EmbeddingData] = []
        prompt_tokens = 0

        try:
            for index, text in enumerate(inputs):
                response = await self._http.post(
                    "/api/embeddings",
                    json={"model": request.model, "prompt": text},
                )
                response.raise_for_status()
                body = response.json()
                embedding = list(body.get("embedding") or [])
                data.append(EmbeddingData(index=index, embedding=embedding))
                prompt_tokens += max(1, len(text) // 4)
        except Exception as exc:
            mapped = map_httpx_exception(exc, provider=PROVIDER_NAME)
            raise map_provider_exception(
                mapped or exc,
                provider=PROVIDER_NAME,
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        return EmbeddingResponse(
            id=f"ollama-emb-{int(time.time())}",
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
