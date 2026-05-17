from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_api_key, get_gateway_service
from app.cache.memory import MemoryCacheClient
from app.main import app
from app.models.user import UserRole
from app.providers.schemas import StreamChunk
from app.schemas.gateway_response import (
    GatewayChoice,
    GatewayMessage,
    GatewayResponse,
    GatewayUsage,
)


@pytest.fixture
def memory_cache() -> MemoryCacheClient:
    return MemoryCacheClient()


@pytest.fixture
def fake_api_key():
    team_id = UUID("77777777-7777-7777-7777-777777777777")
    user_id = UUID("33333333-3333-3333-3333-333333333333")
    team = SimpleNamespace(
        id=team_id,
        slug="platform",
        name="Platform Engineering",
        is_active=True,
    )
    user = SimpleNamespace(
        id=user_id,
        email="admin@example.com",
        full_name="Gateway Administrator",
        role=UserRole.ADMIN,
        is_active=True,
        organization=SimpleNamespace(is_active=True),
    )
    return SimpleNamespace(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        user_id=user_id,
        team_id=team_id,
        team=team,
        user=user,
        is_active=True,
    )


@pytest.fixture
def mock_gateway_response() -> GatewayResponse:
    return GatewayResponse(
        id="mock-integration-1",
        provider="mock",
        model="mock-chat",
        choices=[
            GatewayChoice(
                index=0,
                message=GatewayMessage(role="assistant", content="mock-response: hello"),
                finish_reason="stop",
            )
        ],
        usage=GatewayUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        latency_ms=12.5,
    )


@pytest.fixture
def integration_client(
    memory_cache: MemoryCacheClient,
    fake_api_key,
    mock_gateway_response: GatewayResponse,
):
    gateway = AsyncMock()
    gateway.chat = AsyncMock(return_value=mock_gateway_response)

    async def _stream(*args, **kwargs):
        yield StreamChunk(
            id="stream-1",
            model="mock-chat",
            provider="mock",
            delta="mock-response:",
        )
        yield StreamChunk(
            id="stream-1",
            model="mock-chat",
            provider="mock",
            delta=" hello",
        )
        yield StreamChunk(
            id="stream-1",
            model="mock-chat",
            provider="mock",
            delta="",
            finish_reason="stop",
        )

    gateway.stream = _stream

    app.state.cache = memory_cache
    app.dependency_overrides[get_current_api_key] = lambda: fake_api_key
    app.dependency_overrides[get_gateway_service] = lambda: gateway

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
