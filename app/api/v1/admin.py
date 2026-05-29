from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.permissions import require_admin
from app.config.store import get_config_store
from app.exceptions.gateway import ValidationError
from app.models.user import User
from app.schemas.admin import (
    AuditLogResponse,
    BudgetDashboardResponse,
    ConfigReloadResponse,
    SetAllowedModelsRequest,
    SetProviderPermissionRequest,
    TeamBudgetResponse,
    TeamBudgetUpdateRequest,
    TeamCreateRequest,
    TeamPolicyResponse,
    TeamPolicyUpdateRequest,
    TeamRateLimitResponse,
    TeamRateLimitUpdateRequest,
    TeamResponse,
    UsageSummaryResponse,
)
from app.services.audit_service import AuditService
from app.services.quota_admin_service import QuotaAdminService
from app.services.team_admin_service import TeamAdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/config/reload", response_model=ConfigReloadResponse)
def reload_gateway_config(
    _admin: User = Depends(require_admin),
) -> ConfigReloadResponse:
    store = get_config_store()
    try:
        changed = store.reload(force=True)
    except ValidationError as exc:
        return ConfigReloadResponse(
            reloaded=False,
            path=str(store.path),
            message=str(exc.message),
        )
    return ConfigReloadResponse(
        reloaded=changed,
        path=str(store.path),
        message="Configuration reloaded." if changed else "Configuration unchanged.",
    )


@router.get("/teams", response_model=list[TeamResponse])
def list_teams(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[TeamResponse]:
    teams = TeamAdminService(db).list_teams()
    return [TeamResponse.model_validate(team) for team in teams]


@router.post("/teams", response_model=TeamResponse, status_code=201)
def create_team(
    body: TeamCreateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TeamResponse:
    team = TeamAdminService(db).create_team(body)
    return TeamResponse.model_validate(team)


@router.get("/teams/{team_id}", response_model=TeamResponse)
def get_team(
    team_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TeamResponse:
    team = TeamAdminService(db).get_team(team_id)
    return TeamResponse.model_validate(team)


@router.get("/teams/{team_id}/providers")
def list_team_providers(
    team_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return TeamAdminService(db).list_provider_permissions(team_id)


@router.put("/teams/{team_id}/providers")
def set_team_provider(
    team_id: UUID,
    body: SetProviderPermissionRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return TeamAdminService(db).set_provider_permission(
        team_id,
        provider_id=body.provider_id,
        is_allowed=body.is_allowed,
    )


@router.get("/teams/{team_id}/models")
def list_team_models(
    team_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return TeamAdminService(db).list_allowed_models(team_id)


@router.put("/teams/{team_id}/models")
def set_team_models(
    team_id: UUID,
    body: SetAllowedModelsRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return TeamAdminService(db).set_allowed_models(team_id, body.model_ids)


@router.get("/teams/{team_id}/policy", response_model=TeamPolicyResponse)
def get_team_policy(
    team_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TeamPolicyResponse:
    policy = TeamAdminService(db).get_policy(team_id)
    return TeamPolicyResponse(
        team_id=policy.team_id,
        system_prompt=policy.system_prompt,
        compliance_prompt=policy.compliance_prompt,
        content_filter_config=policy.content_filter_config or {},
        routing_config=policy.routing_config or {},
        enrichment_config=policy.enrichment_config or {},
        is_active=policy.is_active,
        updated_at=policy.updated_at,
    )


@router.put("/teams/{team_id}/policy", response_model=TeamPolicyResponse)
def update_team_policy(
    team_id: UUID,
    body: TeamPolicyUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TeamPolicyResponse:
    policy = TeamAdminService(db).update_policy(team_id, body)
    AuditService(db).record(
        actor=admin,
        action="update",
        resource_type="team_policy",
        resource_id=team_id,
        details=body.model_dump(exclude_unset=True),
    )
    return TeamPolicyResponse(
        team_id=policy.team_id,
        system_prompt=policy.system_prompt,
        compliance_prompt=policy.compliance_prompt,
        content_filter_config=policy.content_filter_config or {},
        routing_config=policy.routing_config or {},
        enrichment_config=policy.enrichment_config or {},
        is_active=policy.is_active,
        updated_at=policy.updated_at,
    )


@router.get("/teams/{team_id}/rate-limit", response_model=TeamRateLimitResponse)
def get_team_rate_limit(
    team_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TeamRateLimitResponse:
    row = QuotaAdminService(db).get_rate_limit(team_id)
    return TeamRateLimitResponse(
        team_id=row.team_id,
        requests_per_minute=row.requests_per_minute,
        tokens_per_minute=row.tokens_per_minute,
        burst_multiplier=float(row.burst_multiplier),
        priority=row.priority.value,
        is_active=row.is_active,
        updated_at=row.updated_at,
    )


@router.put("/teams/{team_id}/rate-limit", response_model=TeamRateLimitResponse)
def update_team_rate_limit(
    team_id: UUID,
    body: TeamRateLimitUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TeamRateLimitResponse:
    row = QuotaAdminService(db).update_rate_limit(team_id, body)
    AuditService(db).record(
        actor=admin,
        action="update",
        resource_type="team_rate_limit",
        resource_id=team_id,
        details=body.model_dump(exclude_unset=True),
    )
    return TeamRateLimitResponse(
        team_id=row.team_id,
        requests_per_minute=row.requests_per_minute,
        tokens_per_minute=row.tokens_per_minute,
        burst_multiplier=float(row.burst_multiplier),
        priority=row.priority.value,
        is_active=row.is_active,
        updated_at=row.updated_at,
    )


@router.get("/teams/{team_id}/budget", response_model=TeamBudgetResponse)
def get_team_budget(
    team_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TeamBudgetResponse:
    row = QuotaAdminService(db).get_budget(team_id)
    return TeamBudgetResponse(
        team_id=row.team_id,
        daily_budget_usd=float(row.daily_budget_usd),
        monthly_budget_usd=float(row.monthly_budget_usd),
        warning_threshold_pct=row.warning_threshold_pct,
        hard_enforcement=row.hard_enforcement,
        is_active=row.is_active,
        updated_at=row.updated_at,
    )


@router.put("/teams/{team_id}/budget", response_model=TeamBudgetResponse)
def update_team_budget(
    team_id: UUID,
    body: TeamBudgetUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TeamBudgetResponse:
    row = QuotaAdminService(db).update_budget(team_id, body)
    AuditService(db).record(
        actor=admin,
        action="update",
        resource_type="team_budget",
        resource_id=team_id,
        details=body.model_dump(exclude_unset=True),
    )
    return TeamBudgetResponse(
        team_id=row.team_id,
        daily_budget_usd=float(row.daily_budget_usd),
        monthly_budget_usd=float(row.monthly_budget_usd),
        warning_threshold_pct=row.warning_threshold_pct,
        hard_enforcement=row.hard_enforcement,
        is_active=row.is_active,
        updated_at=row.updated_at,
    )


@router.get("/teams/{team_id}/budget/dashboard", response_model=BudgetDashboardResponse)
def team_budget_dashboard(
    team_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> BudgetDashboardResponse:
    dashboard = QuotaAdminService(db).budget_dashboard(team_id)
    return BudgetDashboardResponse(
        team_id=dashboard.team_id,
        team_slug=dashboard.team_slug,
        daily_budget_usd=float(dashboard.daily_budget_usd),
        monthly_budget_usd=float(dashboard.monthly_budget_usd),
        daily_spent_usd=float(dashboard.daily_spent_usd),
        monthly_spent_usd=float(dashboard.monthly_spent_usd),
        daily_remaining_usd=float(dashboard.daily_remaining_usd),
        monthly_remaining_usd=float(dashboard.monthly_remaining_usd),
        warning_threshold_pct=dashboard.warning_threshold_pct,
        daily_warning=dashboard.daily_warning,
        monthly_warning=dashboard.monthly_warning,
        hard_enforcement=dashboard.hard_enforcement,
    )


@router.get("/teams/{team_id}/usage", response_model=UsageSummaryResponse)
def team_usage_summary(
    team_id: UUID,
    days: int = 7,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UsageSummaryResponse:
    summary = QuotaAdminService(db).usage_summary(team_id, days=days)
    return UsageSummaryResponse(
        team_id=summary.team_id,
        period_days=summary.period_days,
        request_count=summary.request_count,
        total_tokens=summary.total_tokens,
        total_cost_usd=float(summary.total_cost_usd),
        by_model=summary.by_model,
    )


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[AuditLogResponse]:
    return QuotaAdminService(db).list_audit_logs(limit=limit)
