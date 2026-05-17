from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import AuthenticationError as OpenAIAuthenticationError
from openai import RateLimitError as OpenAIRateLimitError

from app.exceptions import (
    AuthenticationError,
    RateLimitError,
    TimeoutError,
    UnknownProvider,
    ValidationError,
    map_provider_exception,
)
from app.exceptions.base import GatewayError
from app.providers.openai.exceptions import map_openai_exception
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
    assert result.choices[0].message.content == "hello from provider"


@pytest.mark.asyncio
async def test_llm_service_unknown_provider():
    service = LLMService()
    request = GenerateRequest(
        model="x",
        messages=[ChatMessage(role="user", content="hi")],
    )

    with pytest.raises(UnknownProvider):
        await service.generate(request, provider="not-a-provider", api_key="x")


def test_map_openai_auth_error():
    # Construct a minimal stand-in; map by isinstance against OpenAI types when possible.
    class _Auth(OpenAIAuthenticationError):  # type: ignore[misc]
        def __init__(self):
            Exception.__init__(self, "bad key")

    mapped = map_openai_exception(_Auth())
    assert isinstance(mapped, AuthenticationError)
    assert mapped.status_code == 401
    assert mapped.provider == "openai"
    assert mapped.retryable is False


def test_map_openai_rate_limit_error():
    class _Rate(OpenAIRateLimitError):  # type: ignore[misc]
        def __init__(self):
            Exception.__init__(self, "slow down")

    mapped = map_provider_exception(_Rate(), provider="openai")
    assert isinstance(mapped, RateLimitError)
    assert mapped.status_code == 429
    assert mapped.retryable is True


def test_gateway_error_payload_shape():
    err = TimeoutError("Provider request timed out.", provider="openai")
    assert err.to_dict() == {
        "type": "timeout_error",
        "message": "Provider request timed out.",
        "details": None,
        "retryable": True,
        "provider": "openai",
    }
    assert isinstance(err, GatewayError)


def test_validation_error_type():
    err = ValidationError("model is required")
    assert err.error_type == "validation_error"
    assert err.status_code == 400
