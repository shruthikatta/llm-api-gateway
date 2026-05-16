from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_api_key, get_gateway_service
from app.models.api_key import APIKey
from app.providers.schemas import StreamChunk
from app.schemas.chat import ChatCompletionRequest
from app.services.gateway import GatewayService

router = APIRouter(tags=["chat"])


def _sse_chunk(chunk: StreamChunk) -> str:
    payload = {
        "id": chunk.id,
        "object": "chat.completion.chunk",
        "provider": chunk.provider,
        "model": chunk.model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": chunk.delta} if chunk.delta else {},
                "finish_reason": chunk.finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/chat/completions")
async def chat_completion(
    request: ChatCompletionRequest,
    gateway: GatewayService = Depends(get_gateway_service),
    api_key: APIKey = Depends(get_current_api_key),
):

    if request.stream:

        async def event_stream() -> AsyncIterator[str]:
            async for chunk in gateway.stream(request, api_key=api_key):
                yield _sse_chunk(chunk)
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return await gateway.chat(request, api_key=api_key)
