from __future__ import annotations

import pytest

from app.providers.mock.provider import MockProvider
from app.providers.schemas import ChatMessage, EmbeddingRequest, GenerateRequest
from app.services.llm_service import LLMService


@pytest.mark.asyncio
async def test_mock_provider_generate():
    provider = MockProvider(simulated_latency_ms=0)
    response = await provider.generate(
        GenerateRequest(
            model="mock-chat",
            messages=[ChatMessage(role="user", content="ping")],
        )
    )

    assert response.provider == "mock"
    assert response.choices[0].message.content == "mock-response: ping"
    assert response.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_provider_stream():
    provider = MockProvider(simulated_latency_ms=0)
    chunks = [
        chunk
        async for chunk in provider.stream(
            GenerateRequest(
                model="mock-chat",
                messages=[ChatMessage(role="user", content="hi")],
            )
        )
    ]

    text = "".join(chunk.delta for chunk in chunks)
    assert "mock-response: hi" in text
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_mock_provider_embeddings():
    provider = MockProvider(simulated_latency_ms=0)
    response = await provider.embeddings(
        EmbeddingRequest(model="mock-embed", input=["a", "b"], dimensions=4)
    )

    assert response.provider == "mock"
    assert len(response.data) == 2
    assert len(response.data[0].embedding) == 4


@pytest.mark.asyncio
async def test_llm_service_routes_to_mock():
    service = LLMService()
    response = await service.generate(
        GenerateRequest(
            model="mock-chat",
            messages=[ChatMessage(role="user", content="hello")],
        ),
        provider="mock",
    )
    assert response.provider == "mock"
    assert "hello" in response.choices[0].message.content
