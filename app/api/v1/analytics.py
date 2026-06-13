from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.alerts.slack import SlackAlertService
from app.api.deps import get_db
from app.auth.permissions import require_admin
from app.circuit_breaker.service import CircuitBreakerService
from app.config.store import get_config_store
from app.core.config import settings
from app.exceptions.gateway import CircuitOpenError
from app.health.store import ProviderHealthStore
from app.models.user import User
from app.providers.registry import PROVIDER_REGISTRY
from app.schemas.analytics import (
    AlertConfigResponse,
    AlertTestResponse,
    AnalyticsOverviewResponse,
    AnalyticsTimeSeriesPoint,
    AnalyticsTimeSeriesResponse,
    LatencyPercentilesResponse,
    ProviderHealthAnalyticsResponse,
    ProviderHealthListResponse,
    TeamAnalyticsListResponse,
    TeamAnalyticsResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def analytics_overview(
    days: int = 7,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AnalyticsOverviewResponse:
    overview = AnalyticsService(db).platform_overview(days=days)
    return AnalyticsOverviewResponse(
        period_days=days,
        team_count=overview.team_count,
        active_teams=overview.active_teams,
        request_count=overview.request_count,
        success_count=overview.success_count,
        error_count=overview.error_count,
        total_tokens=overview.total_tokens,
        total_cost_usd=float(overview.total_cost_usd),
        avg_latency_ms=overview.avg_latency_ms,
        top_models=overview.top_models,
    )


@router.get("/timeseries", response_model=AnalyticsTimeSeriesResponse)
def analytics_timeseries(
    days: int = 7,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AnalyticsTimeSeriesResponse:
    points = AnalyticsService(db).timeseries(days=days)
    return AnalyticsTimeSeriesResponse(
        period_days=days,
        points=[
            AnalyticsTimeSeriesPoint(
                date=point.date,
                request_count=point.request_count,
                total_tokens=point.total_tokens,
                total_cost_usd=float(point.total_cost_usd),
                avg_latency_ms=point.avg_latency_ms,
            )
            for point in points
        ],
    )


@router.get("/teams", response_model=TeamAnalyticsListResponse)
def analytics_teams(
    days: int = 7,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TeamAnalyticsListResponse:
    teams = AnalyticsService(db).team_breakdown(days=days)
    return TeamAnalyticsListResponse(
        period_days=days,
        teams=[
            TeamAnalyticsResponse(
                team_id=team.team_id,
                team_slug=team.team_slug,
                request_count=team.request_count,
                total_tokens=team.total_tokens,
                total_cost_usd=float(team.total_cost_usd),
                avg_latency_ms=team.avg_latency_ms,
                error_rate=team.error_rate,
            )
            for team in teams
        ],
    )


@router.get("/latency", response_model=LatencyPercentilesResponse)
def analytics_latency(
    days: int = 7,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> LatencyPercentilesResponse:
    percentiles = AnalyticsService(db).latency_percentiles(days=days)
    return LatencyPercentilesResponse(period_days=days, **percentiles)


@router.get("/providers", response_model=ProviderHealthListResponse)
def analytics_providers(
    request: Request,
    _admin: User = Depends(require_admin),
) -> ProviderHealthListResponse:
    config = get_config_store().get()
    cache = request.app.state.cache
    window = config.resilience.circuit_breaker.rolling_window_seconds
    store = ProviderHealthStore(cache, window_seconds=window)
    providers: list[ProviderHealthAnalyticsResponse] = []

    for name in PROVIDER_REGISTRY:
        if not config.provider_enabled(name):
            continue
        circuit_state = "closed"
        try:
            CircuitBreakerService(cache).allow_request(name)
        except CircuitOpenError as exc:
            circuit_state = exc.circuit_state
        snapshot = store.get_snapshot(name, circuit_state=circuit_state)
        providers.append(
            ProviderHealthAnalyticsResponse(
                provider=snapshot.provider,
                healthy=snapshot.healthy and circuit_state != "open",
                latency_ms_ema=snapshot.latency_ms_ema,
                error_rate=snapshot.error_rate,
                circuit_state=circuit_state,
            )
        )

    return ProviderHealthListResponse(providers=providers)


@router.get("/alerts/config", response_model=AlertConfigResponse)
def alert_config(
    _admin: User = Depends(require_admin),
) -> AlertConfigResponse:
    config = get_config_store().get().alerting
    webhook = settings.slack_webhook_url
    slack_configured = webhook is not None and bool(webhook.get_secret_value())
    return AlertConfigResponse(
        enabled=config.enabled,
        budget_warnings=config.budget_warnings,
        circuit_open_alerts=config.circuit_open_alerts,
        error_rate_threshold=config.error_rate_threshold,
        slack_configured=slack_configured,
    )


@router.post("/alerts/test", response_model=AlertTestResponse)
def test_alert(
    _admin: User = Depends(require_admin),
) -> AlertTestResponse:
    service = SlackAlertService()
    if not service.enabled:
        return AlertTestResponse(
            sent=False,
            message="Alerting is disabled or Slack webhook is not configured.",
        )
    sent = service.test_alert()
    return AlertTestResponse(
        sent=sent,
        message="Test alert sent to Slack." if sent else "Failed to send test alert.",
    )
