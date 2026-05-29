from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.exceptions.gateway import NotFoundError
from app.models.api_key import APIKey
from app.models.llm_model import LLMModel
from app.models.quota import RateLimitPriority, TeamBudget, TeamRateLimit
from app.models.team import Team
from app.models.usage_record import UsageRecord
from app.schemas.admin import (
    AuditLogResponse,
    BudgetDashboardResponse,
    TeamBudgetResponse,
    TeamBudgetUpdateRequest,
    TeamRateLimitResponse,
    TeamRateLimitUpdateRequest,
    UsageSummaryResponse,
)
from app.services.audit_service import AuditService
from app.services.team_admin_service import TeamAdminService


class QuotaAdminService:
    def __init__(self, db: Session):
        self._db = db
        self._teams = TeamAdminService(db)

    def get_rate_limit(self, team_id: uuid.UUID) -> TeamRateLimit:
        self._teams.get_team(team_id)
        row = self._db.scalars(
            select(TeamRateLimit).where(TeamRateLimit.team_id == team_id)
        ).first()
        if row is None:
            from app.config.store import get_config_store

            defaults = get_config_store().get().rate_limit
            row = TeamRateLimit(
                team_id=team_id,
                requests_per_minute=defaults.default_requests_per_minute,
                tokens_per_minute=defaults.default_tokens_per_minute,
                burst_multiplier=defaults.default_burst_multiplier,
                priority=RateLimitPriority(defaults.default_priority),
                is_active=True,
            )
            self._db.add(row)
            self._db.flush()
            self._db.refresh(row)
        return row

    def update_rate_limit(
        self,
        team_id: uuid.UUID,
        body: TeamRateLimitUpdateRequest,
    ) -> TeamRateLimit:
        row = self.get_rate_limit(team_id)
        data = body.model_dump(exclude_unset=True)
        if "priority" in data and data["priority"] is not None:
            data["priority"] = RateLimitPriority(data["priority"])
        for key, value in data.items():
            setattr(row, key, value)
        self._db.add(row)
        self._db.flush()
        self._db.refresh(row)
        return row

    def get_budget(self, team_id: uuid.UUID) -> TeamBudget:
        self._teams.get_team(team_id)
        row = self._db.scalars(
            select(TeamBudget).where(TeamBudget.team_id == team_id)
        ).first()
        if row is None:
            from app.config.store import get_config_store

            defaults = get_config_store().get().budget
            row = TeamBudget(
                team_id=team_id,
                daily_budget_usd=defaults.default_daily_budget_usd,
                monthly_budget_usd=defaults.default_monthly_budget_usd,
                warning_threshold_pct=defaults.default_warning_threshold_pct,
                hard_enforcement=defaults.default_hard_enforcement,
                is_active=True,
            )
            self._db.add(row)
            self._db.flush()
            self._db.refresh(row)
        return row

    def update_budget(
        self,
        team_id: uuid.UUID,
        body: TeamBudgetUpdateRequest,
    ) -> TeamBudget:
        row = self.get_budget(team_id)
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        self._db.add(row)
        self._db.flush()
        self._db.refresh(row)
        return row

    def budget_dashboard(self, team_id: uuid.UUID) -> BudgetDashboardResponse:
        team = self._teams.get_team(team_id)
        budget = self.get_budget(team_id)

        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        daily_spent = self._sum_spend(team_id, since=day_start)
        monthly_spent = self._sum_spend(team_id, since=month_start)

        daily_limit = Decimal(str(budget.daily_budget_usd))
        monthly_limit = Decimal(str(budget.monthly_budget_usd))
        threshold = budget.warning_threshold_pct

        return BudgetDashboardResponse(
            team_id=team.id,
            team_slug=team.slug,
            daily_budget_usd=daily_limit,
            monthly_budget_usd=monthly_limit,
            daily_spent_usd=daily_spent,
            monthly_spent_usd=monthly_spent,
            daily_remaining_usd=max(Decimal("0"), daily_limit - daily_spent),
            monthly_remaining_usd=max(Decimal("0"), monthly_limit - monthly_spent),
            warning_threshold_pct=threshold,
            daily_warning=daily_limit > 0
            and daily_spent >= daily_limit * Decimal(threshold) / Decimal(100),
            monthly_warning=monthly_limit > 0
            and monthly_spent >= monthly_limit * Decimal(threshold) / Decimal(100),
            hard_enforcement=budget.hard_enforcement,
        )

    def usage_summary(
        self,
        team_id: uuid.UUID,
        *,
        days: int = 7,
    ) -> UsageSummaryResponse:
        self._teams.get_team(team_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)

        totals = self._db.execute(
            select(
                func.count(UsageRecord.id),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0),
                func.coalesce(func.sum(UsageRecord.total_cost_usd), 0),
            )
            .join(APIKey, UsageRecord.api_key_id == APIKey.id)
            .where(APIKey.team_id == team_id, UsageRecord.created_at >= since)
        ).one()

        by_model_rows = self._db.execute(
            select(
                LLMModel.name,
                func.count(UsageRecord.id),
                func.coalesce(func.sum(UsageRecord.total_cost_usd), 0),
            )
            .join(LLMModel, UsageRecord.model_id == LLMModel.id)
            .join(APIKey, UsageRecord.api_key_id == APIKey.id)
            .where(APIKey.team_id == team_id, UsageRecord.created_at >= since)
            .group_by(LLMModel.name)
            .order_by(func.sum(UsageRecord.total_cost_usd).desc())
        ).all()

        return UsageSummaryResponse(
            team_id=team_id,
            period_days=days,
            request_count=int(totals[0] or 0),
            total_tokens=int(totals[1] or 0),
            total_cost_usd=Decimal(str(totals[2] or 0)),
            by_model=[
                {
                    "model": row[0],
                    "requests": int(row[1]),
                    "cost_usd": Decimal(str(row[2] or 0)),
                }
                for row in by_model_rows
            ],
        )

    def list_audit_logs(self, *, limit: int = 100) -> list[AuditLogResponse]:
        rows = AuditService(self._db).list_recent(limit=limit)
        return [
            AuditLogResponse(
                id=row.id,
                actor_user_id=row.actor_user_id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                details=row.details or {},
                created_at=row.created_at,
            )
            for row in rows
        ]

    def _sum_spend(self, team_id: uuid.UUID, *, since: datetime) -> Decimal:
        value = self._db.scalar(
            select(func.coalesce(func.sum(UsageRecord.total_cost_usd), 0))
            .join(APIKey, UsageRecord.api_key_id == APIKey.id)
            .where(APIKey.team_id == team_id, UsageRecord.created_at >= since)
        )
        return Decimal(str(value or 0))
