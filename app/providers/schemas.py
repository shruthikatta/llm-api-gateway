from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Role = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(slots=True)
class GenerateRequest:
    model: str
    messages: list[ChatMessage]
    temperature: float = 1.0
    max_tokens: int | None = None
    top_p: float | None = None
    stop: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UsageInfo:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(slots=True)
class StreamChunk:
    id: str
    model: str
    provider: str
    delta: str
    finish_reason: str | None = None


@dataclass(slots=True)
class EmbeddingRequest:
    model: str
    input: str | list[str]
    dimensions: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingData:
    index: int
    embedding: list[float]


@dataclass(slots=True)
class EmbeddingResponse:
    id: str
    model: str
    provider: str
    data: list[EmbeddingData]
    usage: UsageInfo
    latency_ms: float
    raw: dict[str, Any] | None = None
