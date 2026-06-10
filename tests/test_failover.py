from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.cache.memory import MemoryCacheClient
from app.exceptions.gateway import AllProvidersFailedError, ProviderError
from app.models.llm_model import LLMModel
from app.models.provider import Provider, ProviderType
from app.models.team import Team
from app.policies.context import ResolvedPolicy
from app.providers.schemas import ChatMessage, GenerateRequest
from app.router.model_router import RouteDecision
from app.schemas.chat import ChatCompletionRequest, Message
from app.schemas.gateway_response import (
    GatewayChoice,
    GatewayMessage,
    GatewayResponse,
    GatewayUsage,
)
from app.services.gateway import GatewayService, PreparedRequest


class _FakeScalars:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _FailoverFakeDB:
    def __init__(self, model: LLMModel | None = None):
        self.model = model

    def scalars(self, statement):
        return _FakeScalars(self.model)

    def get(self, _model, model_id):
        if self.model and self.model.id == model_id:
            return self.model
        return None


@pytest.mark.asyncio
async def test_gateway_failover_to_secondary_provider(monkeypatch):
    provider = Provider(
        id=uuid4(),
        name="OpenAI",
        provider_type=ProviderType.OPENAI,
        base_url="https://api.openai.com/v1",
        is_active=True,
    )
    model = LLMModel(
        id=uuid4(),
        provider_id=provider.id,
        name="gpt-4.1-mini",
        display_name="GPT-4.1 Mini",
        context_window=1048576,
        max_output_tokens=32768,
        input_price_per_million_usd=Decimal("0.50"),
        output_price_per_million_usd=Decimal("1.50"),
        is_active=True,
    )
    model.provider = provider

    expected = GatewayResponse(
        id="mock-1",
        provider="mock",
        model="mock-chat",
        choices=[
            GatewayChoice(
                index=0,
                message=GatewayMessage(role="assistant", content="recovered"),
                finish_reason="stop",
            )
        ],
        usage=GatewayUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5),
        latency_ms=5.0,
    )

    call_log: list[str] = []

    async def _generate(request, *, provider, base_url=None, retry_budget=None):
        call_log.append(provider)
        if provider == "openai":
            raise ProviderError("openai down", provider="openai")
        return expected

    fake_llm = AsyncMock()
    fake_llm.generate = _generate

    team = Team(
        id=uuid4(),
        organization_id=uuid4(),
        name="Platform",
        slug="platform",
        is_active=True,
    )
    routes = [
        RouteDecision(
            model_id=model.id,
            model_name="gpt-4.1-mini",
            provider_id=provider.id,
            provider_name="OpenAI",
            provider_type="openai",
            base_url=provider.base_url,
        ),
        RouteDecision(
            model_id=None,
            model_name="mock-chat",
            provider_id=None,
            provider_name="Mock",
            provider_type="mock",
            base_url="http://localhost",
        ),
    ]
    prepared = PreparedRequest(
        generate_request=GenerateRequest(
            model="gpt-4.1-mini",
            messages=[ChatMessage(role="user", content="hi")],
        ),
        routes=routes,
        policy=ResolvedPolicy(team_id=str(team.id), team_slug="platform"),
        team=team,
        request_id="req_failover",
        model=model,
        estimated_cost_usd=Decimal("0.001"),
        reserved_tokens=128,
    )

    cache = MemoryCacheClient()
    service = GatewayService(_FailoverFakeDB(model), cache)  # type: ignore[arg-type]
    service._llm = SimpleNamespace(generate=fake_llm.generate, stream=AsyncMock())
    monkeypatch.setattr(service, "_prepare", lambda request, api_key: prepared)
    monkeypatch.setattr(service, "_finalize_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_release_reservations", lambda prepared: None)

    response = await service.chat(
        ChatCompletionRequest(model="gpt-4.1-mini", messages=[Message(role="user", content="hi")]),
        api_key=SimpleNamespace(id=uuid4(), user_id=uuid4()),  # type: ignore[arg-type]
    )

    assert response.choices[0].message.content == "recovered"
    assert call_log == ["openai", "mock"]


@pytest.mark.asyncio
async def test_gateway_raises_when_all_providers_fail(monkeypatch):
    team = Team(
        id=uuid4(),
        organization_id=uuid4(),
        name="Platform",
        slug="platform",
        is_active=True,
    )
    routes = [
        RouteDecision(
            model_id=None,
            model_name="mock-chat",
            provider_id=None,
            provider_name="Mock",
            provider_type="mock",
            base_url=None,
        )
    ]
    prepared = PreparedRequest(
        generate_request=GenerateRequest(
            model="mock-chat",
            messages=[ChatMessage(role="user", content="x")],
        ),
        routes=routes,
        policy=ResolvedPolicy(team_id=str(team.id), team_slug="platform"),
        team=team,
        request_id="req_all_fail",
        model=None,
        estimated_cost_usd=Decimal("0"),
        reserved_tokens=64,
    )

    async def _fail(request, *, provider, base_url=None, retry_budget=None):
        raise ProviderError("down", provider="mock")

    cache = MemoryCacheClient()
    service = GatewayService(_FailoverFakeDB(), cache)  # type: ignore[arg-type]
    service._llm = SimpleNamespace(generate=_fail, stream=AsyncMock())
    monkeypatch.setattr(service, "_prepare", lambda request, api_key: prepared)
    monkeypatch.setattr(service, "_release_reservations", lambda prepared: None)

    with pytest.raises(AllProvidersFailedError):
        await service.chat(
            ChatCompletionRequest(model="mock-chat", messages=[Message(role="user", content="x")]),
            api_key=SimpleNamespace(id=uuid4(), user_id=uuid4()),  # type: ignore[arg-type]
        )
