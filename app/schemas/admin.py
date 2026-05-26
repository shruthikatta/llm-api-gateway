from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TeamResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    is_active: bool

    model_config = {"from_attributes": True}


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    organization_id: UUID
    is_active: bool = True


class ProviderPermissionResponse(BaseModel):
    provider_id: UUID
    provider_name: str
    provider_type: str
    is_allowed: bool


class AllowedModelResponse(BaseModel):
    model_id: UUID
    model_name: str
    provider_type: str


class TeamPolicyResponse(BaseModel):
    team_id: UUID
    system_prompt: str | None = None
    compliance_prompt: str | None = None
    content_filter_config: dict[str, Any] = Field(default_factory=dict)
    routing_config: dict[str, Any] = Field(default_factory=dict)
    enrichment_config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TeamPolicyUpdateRequest(BaseModel):
    system_prompt: str | None = None
    compliance_prompt: str | None = None
    content_filter_config: dict[str, Any] | None = None
    routing_config: dict[str, Any] | None = None
    enrichment_config: dict[str, Any] | None = None
    is_active: bool | None = None


class SetProviderPermissionRequest(BaseModel):
    provider_id: UUID
    is_allowed: bool = True


class SetAllowedModelsRequest(BaseModel):
    model_ids: list[UUID] = Field(default_factory=list)


class ConfigReloadResponse(BaseModel):
    reloaded: bool
    path: str
    message: str


class TeamRateLimitResponse(BaseModel):
    team_id: UUID
    requests_per_minute: int
    tokens_per_minute: int
    burst_multiplier: float
    priority: str
    is_active: bool
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TeamRateLimitUpdateRequest(BaseModel):
    requests_per_minute: int | None = Field(default=None, gt=0)
    tokens_per_minute: int | None = Field(default=None, gt=0)
    burst_multiplier: float | None = Field(default=None, gt=0)
    priority: str | None = None
    is_active: bool | None = None


class TeamBudgetResponse(BaseModel):
    team_id: UUID
    daily_budget_usd: float
    monthly_budget_usd: float
    warning_threshold_pct: int
    hard_enforcement: bool
    is_active: bool
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TeamBudgetUpdateRequest(BaseModel):
    daily_budget_usd: float | None = Field(default=None, ge=0)
    monthly_budget_usd: float | None = Field(default=None, ge=0)
    warning_threshold_pct: int | None = Field(default=None, ge=0, le=100)
    hard_enforcement: bool | None = None
    is_active: bool | None = None


class BudgetDashboardResponse(BaseModel):
    team_id: UUID
    team_slug: str
    daily_budget_usd: float
    monthly_budget_usd: float
    daily_spent_usd: float
    monthly_spent_usd: float
    daily_remaining_usd: float
    monthly_remaining_usd: float
    warning_threshold_pct: int
    daily_warning: bool
    monthly_warning: bool
    hard_enforcement: bool


class UsageSummaryResponse(BaseModel):
    team_id: UUID
    period_days: int
    request_count: int
    total_tokens: int
    total_cost_usd: float
    by_model: list[dict[str, Any]]


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any]
    created_at: datetime
