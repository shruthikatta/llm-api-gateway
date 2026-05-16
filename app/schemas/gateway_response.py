from __future__ import annotations

from pydantic import BaseModel, Field


class GatewayMessage(BaseModel):
    role: str
    content: str


class GatewayChoice(BaseModel):
    index: int
    message: GatewayMessage
    finish_reason: str | None = None


class GatewayUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GatewayResponse(BaseModel):
    """
    Provider-agnostic chat completion response.

    Every provider mapper must produce this shape so the API
    contract stays stable when Anthropic/Gemini are added.
    """

    id: str
    provider: str
    model: str
    created: int | None = None
    object: str = "chat.completion"
    choices: list[GatewayChoice] = Field(default_factory=list)
    usage: GatewayUsage
    latency_ms: float
