from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.cache.memory import MemoryCacheClient
from app.services.resilient_llm_service import ResilientLLMService
from app.models.llm_model import LLMModel
from app.models.provider import Provider, ProviderType
from app.models.team import Team
from app.exceptions import ModelNotFoundError
from app.router.model_router import ModelRouter
from app.schemas.chat import ChatCompletionRequest, Message
from app.schemas.gateway_response import (
    GatewayChoice,
    GatewayMessage,
    GatewayResponse,
    GatewayUsage,
)
from app.services.gateway import GatewayService


class _FakeScalars:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value

    def all(self):
        return self._value if isinstance(self._value, list) else [self._value]


class _FakeDB:
    def __init__(self, model: LLMModel | None = None, provider: Provider | None = None):
        self.model = model
        self.provider = provider
        self._call = 0

    def scalars(self, statement):
        self._call += 1
        if self._call == 1:
            return _FakeScalars(self.model)
        return _FakeScalars(self.provider)


def _provider() -> Provider:
    return Provider(
        id=uuid4(),
        name="OpenAI",
        provider_type=ProviderType.OPENAI,
        base_url="https://api.openai.com/v1",
        is_active=True,
    )


def _model(provider: Provider, *, active: bool = True) -> LLMModel:
    from decimal import Decimal

    model = LLMModel(
        id=uuid4(),
        provider_id=provider.id,
        name="gpt-4.1-mini",
        display_name="GPT-4.1 Mini",
        context_window=1048576,
        max_output_tokens=32768,
        input_price_per_million_usd=Decimal("0.50"),
        output_price_per_million_usd=Decimal("1.50"),
        is_active=active,
    )
    model.provider = provider
    return model


def test_model_router_uses_database_record():
    provider = _provider()
    model = _model(provider)
    router = ModelRouter(_FakeDB(model=model))  # type: ignore[arg-type]

    decision = router.resolve("gpt-4.1-mini")

    assert decision.provider_type == "openai"
    assert decision.model_name == "gpt-4.1-mini"
    assert decision.model_id == model.id


def test_model_router_heuristic_for_unregistered_gpt_model():
    provider = _provider()
    router = ModelRouter(_FakeDB(model=None, provider=provider))  # type: ignore[arg-type]

    decision = router.resolve("gpt-5-custom")

    assert decision.provider_type == "openai"
    assert decision.model_id is None
    assert decision.model_name == "gpt-5-custom"


def test_model_router_unknown_model():
    router = ModelRouter(_FakeDB(model=None, provider=None))  # type: ignore[arg-type]

    with pytest.raises(ModelNotFoundError):
        router.resolve("totally-unknown-model")


def test_model_router_heuristic_for_claude_model():
    provider = Provider(
        id=uuid4(),
        name="Anthropic",
        provider_type=ProviderType.ANTHROPIC,
        base_url="https://api.anthropic.com",
        is_active=True,
    )
    router = ModelRouter(_FakeDB(model=None, provider=provider))  # type: ignore[arg-type]

    decision = router.resolve("claude-3-opus")

    assert decision.provider_type == "anthropic"
    assert decision.model_id is None


@pytest.mark.asyncio
async def test_gateway_service_returns_gateway_response(monkeypatch):
    provider = _provider()
    model = _model(provider)
    db = _FakeDB(model=model)

    expected = GatewayResponse(
        id="chatcmpl_1",
        provider="openai",
        model="gpt-4.1-mini",
        created=1752600012,
        choices=[
            GatewayChoice(
                index=0,
                message=GatewayMessage(role="assistant", content="hello"),
                finish_reason="stop",
            )
        ],
        usage=GatewayUsage(
            prompt_tokens=3,
            completion_tokens=1,
            total_tokens=4,
        ),
        latency_ms=12.5,
    )

    fake_llm = AsyncMock()
    fake_llm.generate = AsyncMock(return_value=expected)

    from decimal import Decimal
    from app.policies.context import ResolvedPolicy
    from app.providers.schemas import ChatMessage, GenerateRequest
    from app.router.model_router import RouteDecision
    from app.services.gateway import PreparedRequest

    team = Team(
        id=uuid4(),
        organization_id=uuid4(),
        name="Platform",
        slug="platform",
        is_active=True,
    )
    prepared = PreparedRequest(
        generate_request=GenerateRequest(
            model="gpt-4.1-mini",
            messages=[ChatMessage(role="user", content="hi")],
        ),
        routes=[
            RouteDecision(
                model_id=model.id,
                model_name="gpt-4.1-mini",
                provider_id=provider.id,
                provider_name="OpenAI",
                provider_type="openai",
                base_url=provider.base_url,
            )
        ],
        policy=ResolvedPolicy(team_id=str(team.id), team_slug="platform"),
        team=team,
        request_id="req_test123",
        model=model,
        estimated_cost_usd=Decimal("0.001"),
        reserved_tokens=256,
    )
    monkeypatch.setattr(
        GatewayService,
        "_prepare",
        lambda self, request, api_key: prepared,
    )
    monkeypatch.setattr(
        GatewayService,
        "_finalize_success",
        lambda self, api_key, prepared, response, route: None,
    )
    monkeypatch.setattr(
        GatewayService,
        "_release_reservations",
        lambda self, prepared: None,
    )

    service = GatewayService(
        db=db,
        cache=MemoryCacheClient(),
        llm_service=ResilientLLMService(MemoryCacheClient(), llm_service=fake_llm),
    )  # type: ignore[arg-type]
    body = ChatCompletionRequest(
        model="gpt-4.1-mini",
        messages=[Message(role="user", content="hi")],
    )
    api_key = SimpleNamespace(id=uuid4())

    response = await service.chat(body, api_key=api_key)  # type: ignore[arg-type]

    assert isinstance(response, GatewayResponse)
    assert response.provider == "openai"
    assert response.choices[0].message.content == "hello"
    assert response.usage.total_tokens == 4
    fake_llm.generate.assert_awaited_once()


def test_openai_mapper_normalize_response():
    from app.providers.openai.mapper import OpenAIMapper

    raw = SimpleNamespace(
        id="chatcmpl_abc123",
        model="gpt-4.1-mini",
        created=1752600012,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(role="assistant", content="Hello!"),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=12,
            completion_tokens=18,
            total_tokens=30,
        ),
    )

    normalized = OpenAIMapper().normalize_response(raw, latency_ms=428.5)

    assert normalized.model_dump() == {
        "id": "chatcmpl_abc123",
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "created": 1752600012,
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 18,
            "total_tokens": 30,
        },
        "latency_ms": 428.5,
    }
