from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from decimal import Decimal

import pytest

from app.cache.memory import MemoryCacheClient
from app.models.llm_model import LLMModel
from app.models.provider import Provider, ProviderType
from app.models.team import Team
from app.policies.context import ResolvedPolicy
from app.providers.schemas import ChatMessage, GenerateRequest, StreamChunk
from app.router.model_router import RouteDecision
from app.schemas.chat import ChatCompletionRequest, Message
from app.services.gateway import GatewayService, PreparedRequest
from app.services.resilient_llm_service import ResilientLLMService


class _FakeScalars:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _FakeDB:
    def __init__(self, model: LLMModel | None = None):
        self.model = model

    def scalars(self, statement):
        return _FakeScalars(self.model)


@pytest.mark.asyncio
async def test_gateway_service_stream(monkeypatch):
    provider = Provider(
        id=uuid4(),
        name="Mock",
        provider_type=ProviderType.MOCK,
        base_url="http://localhost",
        is_active=True,
    )
    from decimal import Decimal

    model = LLMModel(
        id=uuid4(),
        provider_id=provider.id,
        name="mock-chat",
        display_name="Mock Chat",
        context_window=8192,
        max_output_tokens=2048,
        input_price_per_million_usd=Decimal("0.50"),
        output_price_per_million_usd=Decimal("1.50"),
        is_active=True,
    )
    model.provider = provider

    async def _stream(*args, **kwargs):
        yield StreamChunk(
            id="s1",
            model="mock-chat",
            provider="mock",
            delta="hi",
        )
        yield StreamChunk(
            id="s1",
            model="mock-chat",
            provider="mock",
            delta="",
            finish_reason="stop",
        )

    fake_llm = AsyncMock()
    fake_llm.stream = _stream

    team = Team(
        id=uuid4(),
        organization_id=uuid4(),
        name="Platform",
        slug="platform",
        is_active=True,
    )
    prepared = PreparedRequest(
        generate_request=GenerateRequest(
            model="mock-chat",
            messages=[ChatMessage(role="user", content="x")],
        ),
        routes=[
            RouteDecision(
                model_id=model.id,
                model_name="mock-chat",
                provider_id=provider.id,
                provider_name="Mock",
                provider_type="mock",
                base_url=provider.base_url,
            )
        ],
        policy=ResolvedPolicy(team_id=str(team.id), team_slug="platform"),
        team=team,
        request_id="req_stream1",
        model=model,
        estimated_cost_usd=Decimal("0.0001"),
        reserved_tokens=128,
    )
    monkeypatch.setattr(
        GatewayService,
        "_prepare",
        lambda self, request, api_key: prepared,
    )

    async def _stream_no_accounting(self, request, *, api_key):
        prepared = prepared_holder["value"]
        async for chunk in fake_llm.stream(
            prepared.generate_request,
            provider=prepared.route.provider_type,
            base_url=prepared.route.base_url,
        ):
            if chunk.delta:
                yield StreamChunk(
                    id=chunk.id,
                    model=chunk.model,
                    provider=chunk.provider,
                    delta=chunk.delta,
                    finish_reason=chunk.finish_reason,
                )
            else:
                yield chunk

    prepared_holder = {"value": prepared}
    monkeypatch.setattr(GatewayService, "stream", _stream_no_accounting)

    service = GatewayService(
        db=_FakeDB(model),
        cache=MemoryCacheClient(),
        llm_service=ResilientLLMService(MemoryCacheClient(), llm_service=fake_llm),
    )  # type: ignore[arg-type]
    chunks = [
        chunk
        async for chunk in service.stream(
            ChatCompletionRequest(
                model="mock-chat",
                messages=[Message(role="user", content="x")],
                stream=True,
            ),
            api_key=SimpleNamespace(id=uuid4()),  # type: ignore[arg-type]
        )
    ]

    assert chunks[0].delta == "hi"
    assert chunks[-1].finish_reason == "stop"
