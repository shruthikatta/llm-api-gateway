from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RateLimitPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TeamRateLimit(Base):
    """Per-team distributed rate limit configuration."""

    __tablename__ = "team_rate_limits"
    __table_args__ = (UniqueConstraint("team_id", name="uq_team_rate_limit_team"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    requests_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    tokens_per_minute: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100_000,
    )
    burst_multiplier: Mapped[float] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        default=2.0,
    )
    priority: Mapped[RateLimitPriority] = mapped_column(
        Enum(RateLimitPriority, name="rate_limit_priority"),
        nullable=False,
        default=RateLimitPriority.NORMAL,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    team = relationship("Team", back_populates="rate_limit")


class TeamBudget(Base):
    """Per-team spend limits and enforcement policy."""

    __tablename__ = "team_budgets"
    __table_args__ = (UniqueConstraint("team_id", name="uq_team_budget_team"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    daily_budget_usd: Mapped[float] = mapped_column(
        Numeric(12, 4),
        nullable=False,
        default=100.0,
    )
    monthly_budget_usd: Mapped[float] = mapped_column(
        Numeric(12, 4),
        nullable=False,
        default=1000.0,
    )
    warning_threshold_pct: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=80,
    )
    hard_enforcement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    team = relationship("Team", back_populates="budget")


class AuditLog(Base):
    """Immutable record of administrative mutations."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    actor = relationship("User")


Index("ix_audit_logs_actor", AuditLog.actor_user_id)
Index("ix_audit_logs_resource", AuditLog.resource_type, AuditLog.resource_id)
Index("ix_audit_logs_created_at", AuditLog.created_at)
