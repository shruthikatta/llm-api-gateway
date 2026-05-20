from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Team(Base):
    """Engineering team within an organization — primary policy boundary."""

    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_teams_org_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
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

    organization = relationship("Organization", back_populates="teams")
    api_keys = relationship("APIKey", back_populates="team")
    provider_permissions = relationship(
        "TeamProviderPermission",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    allowed_models = relationship(
        "TeamAllowedModel",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    policy = relationship(
        "TeamPolicy",
        back_populates="team",
        uselist=False,
        cascade="all, delete-orphan",
    )
    rate_limit = relationship(
        "TeamRateLimit",
        back_populates="team",
        uselist=False,
        cascade="all, delete-orphan",
    )
    budget = relationship(
        "TeamBudget",
        back_populates="team",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TeamProviderPermission(Base):
    """Explicit allow/deny of a provider for a team (extensible beyond OpenAI)."""

    __tablename__ = "team_provider_permissions"
    __table_args__ = (
        UniqueConstraint("team_id", "provider_id", name="uq_team_provider"),
    )

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
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    team = relationship("Team", back_populates="provider_permissions")
    provider = relationship("Provider")


class TeamAllowedModel(Base):
    """Allow-list of models a team may call. Empty list = deny all."""

    __tablename__ = "team_allowed_models"
    __table_args__ = (UniqueConstraint("team_id", "model_id", name="uq_team_model"),)

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
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("llm_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    team = relationship("Team", back_populates="allowed_models")
    model = relationship("LLMModel")


class TeamPolicy(Base):
    """
    Per-team request policy: prompts, filters, routing, enrichment.

    JSONB configs stay provider-agnostic so Anthropic/etc. can reuse them later.
    """

    __tablename__ = "team_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    compliance_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_filter_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    routing_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    enrichment_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
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

    team = relationship("Team", back_populates="policy")


Index("ix_teams_org", Team.organization_id)
Index("ix_teams_active", Team.is_active)
Index("ix_team_provider_permissions_team", TeamProviderPermission.team_id)
Index("ix_team_allowed_models_team", TeamAllowedModel.team_id)
