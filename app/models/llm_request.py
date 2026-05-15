from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RequestStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


class LLMRequest(Base):
    __tablename__ = "llm_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )

    request_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("llm_models.id", ondelete="RESTRICT"),
        nullable=False,
    )

    model = relationship(
        "LLMModel",
    )

    endpoint: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        nullable=False,
    )

    provider_request_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="requests",
    )

    usage = relationship(
        "UsageRecord",
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
    )

    api_key = relationship(
        "APIKey",
        back_populates="requests",
    )


Index("ix_llm_requests_user", LLMRequest.user_id)
Index("ix_llm_requests_api_key", LLMRequest.api_key_id)
Index("ix_llm_requests_status", LLMRequest.status)
Index("ix_llm_requests_created_at", LLMRequest.created_at)
Index("ix_llm_requests_model", LLMRequest.model_id)