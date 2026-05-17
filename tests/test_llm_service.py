from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.exceptions import UnknownProvider
from app.providers.schemas import ChatMessage, GenerateRequest
from app.schemas.gateway_response import GatewayResponse
from app.services.llm_service import LLMService


def _fake_openai_response():
    return SimpleNamespace(
        id="chatcmpl_test",
        model="gpt-4.1-mini",
        created=1752600012,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content="hello from provider",
                ),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=4,
            total_tokens=14,
        ),
    )


@pytest.mark.asyncio
async def test_llm_service_generate_returns_gateway_response(monkeypatch):
    from app.providers.openai import provider as openai_provider_module
    from app.providers.openai.client import OpenAIClient

    fake_client = AsyncMock(spec=OpenAIClient)
    fake_client.chat = AsyncMock(return_value=_fake_openai_response())

    original_init = openai_provider_module.OpenAIProvider.__init__

    def patched_init(self, api_key, **kwargs):
        original_init(self, api_key=api_key, client=fake_client, **kwargs)

    monkeypatch.setattr(
        openai_provider_module.OpenAIProvider,
        "__init__",
        patched_init,
    )

    service = LLMService()
    request = GenerateRequest(
        model="gpt-4.1-mini",
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.2,
        max_tokens=32,
    )

    result = await service.generate(
        request,
        provider="openai",
        api_key="test-key",
    )

    assert isinstance(result, GatewayResponse)
    assert result.provider == "openai"
    assert result.model == "gpt-4.1-mini"
    assert result.created == 1752600012
    assert result.choices[0].message.role == "assistant"
    assert result.choices[0].message.content == "hello from provider"
    assert result.usage.total_tokens == 14
    assert result.latency_ms >= 0
    fake_client.chat.assert_awaited_once()

    import app.services.llm_service as llm_service_module

    source = open(llm_service_module.__file__).read()
    assert "from openai" not in source
    assert "import openai" not in source


@pytest.mark.asyncio
async def test_llm_service_unknown_provider():
    service = LLMService()
    request = GenerateRequest(
        model="x",
        messages=[ChatMessage(role="user", content="hi")],
    )

    with pytest.raises(UnknownProvider):
        await service.generate(request, provider="not-a-provider", api_key="x")
