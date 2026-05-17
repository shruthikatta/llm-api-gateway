from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.providers.anthropic.provider import AnthropicProvider
from app.providers.http import AsyncHttpClient
from app.providers.ollama.provider import OllamaProvider
from app.providers.schemas import ChatMessage, GenerateRequest


@pytest.mark.asyncio
async def test_anthropic_generate_normalizes_response():
    payload = {
        "id": "msg_123",
        "model": "claude-sonnet-4-20250514",
        "content": [{"type": "text", "text": "bonjour"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 2},
    }
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(200, json=payload, request=request)
    http_client = AsyncMock(spec=AsyncHttpClient)
    http_client.post = AsyncMock(return_value=response)

    provider = AnthropicProvider(
        api_key="test-key",
        http_client=http_client,
    )
    result = await provider.generate(
        GenerateRequest(
            model="claude-sonnet-4-20250514",
            messages=[
                ChatMessage(role="system", content="be brief"),
                ChatMessage(role="user", content="hi"),
            ],
            max_tokens=64,
        )
    )

    assert result.provider == "anthropic"
    assert result.choices[0].message.content == "bonjour"
    assert result.usage.prompt_tokens == 5
    assert result.usage.completion_tokens == 2
    http_client.post.assert_awaited_once()
    kwargs = http_client.post.await_args.kwargs
    assert kwargs["json"]["system"] == "be brief"
    assert kwargs["json"]["messages"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_ollama_generate_normalizes_response():
    payload = {
        "model": "llama3.2",
        "created_at": "2026-07-16T00:00:00Z",
        "message": {"role": "assistant", "content": "hola"},
        "done": True,
        "prompt_eval_count": 3,
        "eval_count": 1,
    }
    request = httpx.Request("POST", "http://localhost:11434/api/chat")
    response = httpx.Response(200, json=payload, request=request)
    http_client = AsyncMock(spec=AsyncHttpClient)
    http_client.post = AsyncMock(return_value=response)

    provider = OllamaProvider(http_client=http_client)
    result = await provider.generate(
        GenerateRequest(
            model="llama3.2",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )

    assert result.provider == "ollama"
    assert result.choices[0].message.content == "hola"
    assert result.usage.total_tokens == 4


@pytest.mark.asyncio
async def test_anthropic_stream_parses_sse_events():
    lines = [
        'data: {"type":"message_start","message":{"id":"msg_1","model":"claude-x"}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hel"}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"lo"}}',
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
    ]

    class _Stream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for line in lines:
                yield line

    http_client = AsyncMock(spec=AsyncHttpClient)
    http_client.stream = lambda *args, **kwargs: _Stream()

    provider = AnthropicProvider(api_key="test-key", http_client=http_client)
    chunks = [
        chunk
        async for chunk in provider.stream(
            GenerateRequest(
                model="claude-x",
                messages=[ChatMessage(role="user", content="hi")],
            )
        )
    ]

    assert "".join(c.delta for c in chunks) == "Hello"
    assert chunks[-1].finish_reason == "end_turn"
