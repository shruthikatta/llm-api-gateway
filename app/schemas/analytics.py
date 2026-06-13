from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsOverviewResponse(BaseModel):
    period_days: int
    team_count: int
    active_teams: int
    request_count: int
    success_count: int
    error_count: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    top_models: list[dict[str, Any]]


class AnalyticsTimeSeriesPoint(BaseModel):
    date: str
    request_count: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float


class AnalyticsTimeSeriesResponse(BaseModel):
    period_days: int
    points: list[AnalyticsTimeSeriesPoint]


class TeamAnalyticsResponse(BaseModel):
    team_id: UUID
    team_slug: str
    request_count: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    error_rate: float


class TeamAnalyticsListResponse(BaseModel):
    period_days: int
    teams: list[TeamAnalyticsResponse]


class LatencyPercentilesResponse(BaseModel):
    period_days: int
    p50_ms: float
    p95_ms: float
    p99_ms: float


class ProviderHealthAnalyticsResponse(BaseModel):
    provider: str
    healthy: bool
    latency_ms_ema: float
    error_rate: float
    circuit_state: str


class ProviderHealthListResponse(BaseModel):
    providers: list[ProviderHealthAnalyticsResponse]


class AlertTestResponse(BaseModel):
    sent: bool
    message: str


class AlertConfigResponse(BaseModel):
    enabled: bool
    budget_warnings: bool
    circuit_open_alerts: bool
    error_rate_threshold: float
    slack_configured: bool
