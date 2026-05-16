from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message] = Field(min_length=1)
    temperature: float | None = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stop: str | list[str] | None = None
    stream: bool = False
    user: str | None = None
    metadata: dict[str, Any] | None = None
