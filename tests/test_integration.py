from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.cache.memory import MemoryCacheClient
from app.exceptions.gateway import ProviderError
from app.main import app
from app.providers.mock.provider import MockProvider
from app.providers.schemas import ChatMessage, GenerateRequest
from app.services.resilient_llm_service import ResilientLLMService


def test_live_endpoint():
    client = TestClient(app)
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_chat_completion_integration(integration_client: TestClient):
    response = integration_client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={
            "model": "mock-chat",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["choices"][0]["message"]["content"] == "mock-response: hello"
    assert body["usage"]["total_tokens"] == 15


def test_chat_streaming_integration(integration_client: TestClient):
    with integration_client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json={
            "model": "mock-chat",
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    ) as response:
        assert response.status_code == 200
        chunks = list(response.iter_lines())
    assert any("mock-response:" in chunk for chunk in chunks)
    assert any("[DONE]" in chunk for chunk in chunks)


def test_chat_requires_auth():
    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "mock-chat",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 401


def test_me_endpoint(integration_client: TestClient):
    response = integration_client.get(
        "/v1/me",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@example.com"
    assert body["role"] == "admin"
    assert body["team_slug"] == "platform"


def test_metrics_and_dashboard_available():
    client = TestClient(app)
    metrics = client.get("/metrics")
    dashboard = client.get("/dashboard")
    assert metrics.status_code == 200
    assert "gateway_requests_total" in metrics.text
    assert dashboard.status_code == 200
    assert "LLM API Gateway" in dashboard.text


@pytest.mark.asyncio
async def test_mock_provider_recovery_after_fault():
    provider = MockProvider(simulated_latency_ms=0, chaos_always_fail=True)
    with pytest.raises(ProviderError):
        await provider.generate(
            GenerateRequest(
                model="mock-chat",
                messages=[ChatMessage(role="user", content="fail")],
            )
        )

    provider = MockProvider(simulated_latency_ms=0, chaos_always_fail=False)
    response = await provider.generate(
        GenerateRequest(
            model="mock-chat",
            messages=[ChatMessage(role="user", content="recover")],
        )
    )
    assert response.choices[0].message.content == "mock-response: recover"


@pytest.mark.asyncio
async def test_concurrent_mock_streams():
    provider = MockProvider(simulated_latency_ms=1)

    async def _one_stream() -> str:
        chunks = [
            chunk
            async for chunk in provider.stream(
                GenerateRequest(
                    model="mock-chat",
                    messages=[ChatMessage(role="user", content="stress")],
                )
            )
        ]
        return "".join(chunk.delta for chunk in chunks)

    results = await asyncio.gather(*[_one_stream() for _ in range(50)])
    assert all("mock-response: stress" in text for text in results)


@pytest.mark.asyncio
async def test_resilient_service_records_health_on_success():
    cache = MemoryCacheClient()
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value=type(
            "R",
            (),
            {
                "id": "x",
                "provider": "mock",
                "model": "mock-chat",
                "choices": [],
                "usage": type("U", (), {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})(),
                "latency_ms": 1.0,
            },
        )()
    )
    service = ResilientLLMService(cache, llm_service=llm)
    await service.generate(
        GenerateRequest(
            model="mock-chat",
            messages=[ChatMessage(role="user", content="ok")],
        ),
        provider="mock",
    )
    snapshot = service._health.get_snapshot("mock")  # noqa: SLF001
    assert snapshot.healthy is True
    assert snapshot.latency_ms_ema >= 0
