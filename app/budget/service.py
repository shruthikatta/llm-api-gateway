from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cache import CacheClient
from app.cache.redis_client import CacheUnavailableError
from app.config.store import get_config_store
from app.exceptions.gateway import BudgetExceededError
from app.models.quota import TeamBudget
from app.models.usage_record import UsageRecord
from app.budget.store import check_and_increment
from app.telemetry.metrics import BUDGET_EXCEEDED_TOTAL

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400
SECONDS_PER_MONTH = 2_592_000


@dataclass(slots=True, frozen=True)
class BudgetStatus:
    daily_spent_usd: float
    monthly_spent_usd: float
    daily_limit_usd: float
    monthly_limit_usd: float
    warning_threshold_pct: int
    daily_warning: bool
    monthly_warning: bool


class BudgetService:
    """Atomic budget enforcement using Redis counters with DB reconciliation."""

    def __init__(self, db: Session, cache: CacheClient):
        self._db = db
        self._cache = cache

    def check_and_reserve(
        self,
        team_id: uuid.UUID,
        estimated_cost_usd: float,
        *,
        request_id: str | None = None,
    ) -> None:
        if estimated_cost_usd <= 0:
            return

        config = self._resolve_config(team_id)
        if not config.is_active:
            return

        daily_key = self._daily_key(team_id)
        monthly_key = self._monthly_key(team_id)

        try:
            daily_ok, daily_spent = check_and_increment(
                self._cache,
                key=daily_key,
                limit=float(config.daily_budget_usd),
                amount=estimated_cost_usd,
                ttl_seconds=SECONDS_PER_DAY * 2,
            )
            if not daily_ok and config.hard_enforcement:
                BUDGET_EXCEEDED_TOTAL.labels(team_slug=str(team_id)).inc()
                raise BudgetExceededError(
                    "Daily budget exceeded.",
                    period="daily",
                    limit_usd=float(config.daily_budget_usd),
                    spent_usd=daily_spent,
                    request_id=request_id,
                )

            monthly_ok, monthly_spent = check_and_increment(
                self._cache,
                key=monthly_key,
                limit=float(config.monthly_budget_usd),
                amount=estimated_cost_usd,
                ttl_seconds=SECONDS_PER_MONTH * 2,
            )
            if not monthly_ok and config.hard_enforcement:
                self._refund(daily_key, estimated_cost_usd)
                BUDGET_EXCEEDED_TOTAL.labels(team_slug=str(team_id)).inc()
                raise BudgetExceededError(
                    "Monthly budget exceeded.",
                    period="monthly",
                    limit_usd=float(config.monthly_budget_usd),
                    spent_usd=monthly_spent,
                    request_id=request_id,
                )
        except CacheUnavailableError:
            if not self._db_budget_check(team_id, estimated_cost_usd, config):
                raise BudgetExceededError(
                    "Budget exceeded.",
                    period="daily",
                    limit_usd=float(config.daily_budget_usd),
                    spent_usd=0.0,
                    request_id=request_id,
                ) from None

    def reconcile_actual_cost(
        self,
        team_id: uuid.UUID,
        *,
        estimated_cost_usd: float,
        actual_cost_usd: float,
    ) -> None:
        delta = actual_cost_usd - estimated_cost_usd
        if abs(delta) < 1e-9:
            return

        daily_key = self._daily_key(team_id)
        monthly_key = self._monthly_key(team_id)
        try:
            if delta > 0:
                config = self._resolve_config(team_id)
                check_and_increment(
                    self._cache,
                    key=daily_key,
                    limit=float(config.daily_budget_usd) + delta,
                    amount=delta,
                    ttl_seconds=SECONDS_PER_DAY * 2,
                )
                check_and_increment(
                    self._cache,
                    key=monthly_key,
                    limit=float(config.monthly_budget_usd) + delta,
                    amount=delta,
                    ttl_seconds=SECONDS_PER_MONTH * 2,
                )
            else:
                self._refund(daily_key, -delta)
                self._refund(monthly_key, -delta)
        except CacheUnavailableError:
            logger.warning(
                "Budget reconciliation skipped: cache unavailable team=%s",
                team_id,
            )

    def get_status(self, team_id: uuid.UUID) -> BudgetStatus:
        config = self._resolve_config(team_id)
        daily_spent = self._read_counter(self._daily_key(team_id))
        monthly_spent = self._read_counter(self._monthly_key(team_id))

        if daily_spent == 0.0 and monthly_spent == 0.0:
            daily_spent, monthly_spent = self._db_spend_totals(team_id)

        daily_limit = float(config.daily_budget_usd)
        monthly_limit = float(config.monthly_budget_usd)
        threshold = config.warning_threshold_pct

        return BudgetStatus(
            daily_spent_usd=daily_spent,
            monthly_spent_usd=monthly_spent,
            daily_limit_usd=daily_limit,
            monthly_limit_usd=monthly_limit,
            warning_threshold_pct=threshold,
            daily_warning=daily_limit > 0 and daily_spent >= daily_limit * threshold / 100,
            monthly_warning=monthly_limit > 0
            and monthly_spent >= monthly_limit * threshold / 100,
        )

    def _resolve_config(self, team_id: uuid.UUID) -> TeamBudget:
        row = self._db.scalars(
            select(TeamBudget).where(
                TeamBudget.team_id == team_id,
                TeamBudget.is_active.is_(True),
            )
        ).first()
        if row is not None:
            return row

        defaults = get_config_store().get().budget
        return TeamBudget(
            team_id=team_id,
            daily_budget_usd=defaults.default_daily_budget_usd,
            monthly_budget_usd=defaults.default_monthly_budget_usd,
            warning_threshold_pct=defaults.default_warning_threshold_pct,
            hard_enforcement=defaults.default_hard_enforcement,
            is_active=True,
        )

    def _db_budget_check(
        self,
        team_id: uuid.UUID,
        amount: float,
        config: TeamBudget,
    ) -> bool:
        if not config.hard_enforcement:
            return True

        daily_spent, monthly_spent = self._db_spend_totals(team_id)
        if daily_spent + amount > float(config.daily_budget_usd):
            return False
        if monthly_spent + amount > float(config.monthly_budget_usd):
            return False
        return True

    def _db_spend_totals(self, team_id: uuid.UUID) -> tuple[float, float]:
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        from app.models.api_key import APIKey

        daily = self._db.scalar(
            select(func.coalesce(func.sum(UsageRecord.total_cost_usd), 0))
            .join(APIKey, UsageRecord.api_key_id == APIKey.id)
            .where(APIKey.team_id == team_id, UsageRecord.created_at >= day_start)
        )
        monthly = self._db.scalar(
            select(func.coalesce(func.sum(UsageRecord.total_cost_usd), 0))
            .join(APIKey, UsageRecord.api_key_id == APIKey.id)
            .where(APIKey.team_id == team_id, UsageRecord.created_at >= month_start)
        )
        return float(daily or 0), float(monthly or 0)

    def _read_counter(self, key: str) -> float:
        try:
            raw = self._cache.get(key)
            return float(raw) if raw is not None else 0.0
        except CacheUnavailableError:
            return 0.0

    def _refund(self, key: str, amount: float) -> None:
        if amount <= 0:
            return
        try:
            check_and_increment(
                self._cache,
                key=key,
                limit=1e18,
                amount=-amount,
                ttl_seconds=SECONDS_PER_DAY * 2,
            )
        except CacheUnavailableError:
            logger.warning("Budget refund skipped for key=%s", key)

    def _daily_key(self, team_id: uuid.UUID) -> str:
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"budget:daily:{team_id}:{day}"

    def _monthly_key(self, team_id: uuid.UUID) -> str:
        month = datetime.now(timezone.utc).strftime("%Y%m")
        return f"budget:monthly:{team_id}:{month}"
