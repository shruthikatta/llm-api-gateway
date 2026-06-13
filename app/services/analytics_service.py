from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.api_key import APIKey
from app.models.llm_model import LLMModel
from app.models.llm_request import LLMRequest, RequestStatus
from app.models.team import Team
from app.models.usage_record import UsageRecord
from app.services.team_admin_service import TeamAdminService


@dataclass(slots=True)
class PlatformOverview:
    team_count: int
    active_teams: int
    request_count: int
    success_count: int
    error_count: int
    total_tokens: int
    total_cost_usd: Decimal
    avg_latency_ms: float
    top_models: list[dict]


@dataclass(slots=True)
class TimeSeriesPoint:
    date: str
    request_count: int
    total_tokens: int
    total_cost_usd: Decimal
    avg_latency_ms: float


@dataclass(slots=True)
class TeamAnalytics:
    team_id: uuid.UUID
    team_slug: str
    request_count: int
    total_tokens: int
    total_cost_usd: Decimal
    avg_latency_ms: float
    error_rate: float


class AnalyticsService:
    """Aggregate usage and latency analytics for admin dashboards."""

    def __init__(self, db: Session):
        self._db = db
        self._teams = TeamAdminService(db)

    def platform_overview(self, *, days: int = 7) -> PlatformOverview:
        since = self._since(days)
        teams = self._db.scalars(select(Team)).all()
        active_teams = sum(1 for team in teams if team.is_active)

        totals = self._db.execute(
            select(
                func.count(LLMRequest.id),
                func.coalesce(
                    func.sum(
                        case((LLMRequest.status == RequestStatus.SUCCESS, 1), else_=0)
                    ),
                    0,
                ),
                func.coalesce(func.sum(LLMRequest.total_tokens), 0),
                func.coalesce(func.avg(LLMRequest.latency_ms), 0),
            ).where(LLMRequest.created_at >= since)
        ).one()

        cost = self._db.scalar(
            select(func.coalesce(func.sum(UsageRecord.total_cost_usd), 0)).where(
                UsageRecord.created_at >= since
            )
        )

        top_models = self._db.execute(
            select(
                LLMModel.name,
                func.count(UsageRecord.id),
                func.coalesce(func.sum(UsageRecord.total_cost_usd), 0),
            )
            .join(LLMModel, UsageRecord.model_id == LLMModel.id)
            .where(UsageRecord.created_at >= since)
            .group_by(LLMModel.name)
            .order_by(func.sum(UsageRecord.total_cost_usd).desc())
            .limit(5)
        ).all()

        request_count = int(totals[0] or 0)
        success_count = int(totals[1] or 0)

        return PlatformOverview(
            team_count=len(teams),
            active_teams=active_teams,
            request_count=request_count,
            success_count=success_count,
            error_count=max(0, request_count - success_count),
            total_tokens=int(totals[2] or 0),
            total_cost_usd=Decimal(str(cost or 0)),
            avg_latency_ms=float(totals[3] or 0),
            top_models=[
                {
                    "model": row[0],
                    "requests": int(row[1]),
                    "cost_usd": float(row[2] or 0),
                }
                for row in top_models
            ],
        )

    def timeseries(self, *, days: int = 7) -> list[TimeSeriesPoint]:
        since = self._since(days)
        rows = self._db.execute(
            select(
                func.date_trunc("day", LLMRequest.created_at).label("day"),
                func.count(LLMRequest.id),
                func.coalesce(func.sum(LLMRequest.total_tokens), 0),
                func.coalesce(func.avg(LLMRequest.latency_ms), 0),
            )
            .where(LLMRequest.created_at >= since)
            .group_by("day")
            .order_by("day")
        ).all()

        cost_by_day = {
            row[0].date().isoformat(): Decimal(str(row[1] or 0))
            for row in self._db.execute(
                select(
                    func.date_trunc("day", UsageRecord.created_at).label("day"),
                    func.coalesce(func.sum(UsageRecord.total_cost_usd), 0),
                )
                .where(UsageRecord.created_at >= since)
                .group_by("day")
            ).all()
        }

        points: list[TimeSeriesPoint] = []
        for row in rows:
            day = row[0].date().isoformat()
            points.append(
                TimeSeriesPoint(
                    date=day,
                    request_count=int(row[1]),
                    total_tokens=int(row[2] or 0),
                    total_cost_usd=cost_by_day.get(day, Decimal("0")),
                    avg_latency_ms=float(row[3] or 0),
                )
            )
        return points

    def team_breakdown(self, *, days: int = 7) -> list[TeamAnalytics]:
        since = self._since(days)
        rows = self._db.execute(
            select(
                Team.id,
                Team.slug,
                func.count(LLMRequest.id),
                func.coalesce(func.sum(LLMRequest.total_tokens), 0),
                func.coalesce(func.avg(LLMRequest.latency_ms), 0),
                func.coalesce(
                    func.sum(
                        case((LLMRequest.status != RequestStatus.SUCCESS, 1), else_=0)
                    ),
                    0,
                ),
            )
            .join(APIKey, APIKey.team_id == Team.id)
            .join(LLMRequest, LLMRequest.api_key_id == APIKey.id)
            .where(LLMRequest.created_at >= since)
            .group_by(Team.id, Team.slug)
            .order_by(func.count(LLMRequest.id).desc())
        ).all()

        cost_by_team: dict[uuid.UUID, Decimal] = {
            row[0]: Decimal(str(row[1] or 0))
            for row in self._db.execute(
                select(
                    APIKey.team_id,
                    func.coalesce(func.sum(UsageRecord.total_cost_usd), 0),
                )
                .join(UsageRecord, UsageRecord.api_key_id == APIKey.id)
                .where(UsageRecord.created_at >= since)
                .group_by(APIKey.team_id)
            ).all()
        }

        results: list[TeamAnalytics] = []
        for row in rows:
            request_count = int(row[2] or 0)
            error_count = int(row[5] or 0)
            results.append(
                TeamAnalytics(
                    team_id=row[0],
                    team_slug=row[1],
                    request_count=request_count,
                    total_tokens=int(row[3] or 0),
                    total_cost_usd=cost_by_team.get(row[0], Decimal("0")),
                    avg_latency_ms=float(row[4] or 0),
                    error_rate=(error_count / request_count) if request_count else 0.0,
                )
            )
        return results

    def latency_percentiles(self, *, days: int = 7) -> dict[str, float]:
        since = self._since(days)
        latencies = [
            float(value)
            for value in self._db.scalars(
                select(LLMRequest.latency_ms)
                .where(
                    LLMRequest.created_at >= since,
                    LLMRequest.status == RequestStatus.SUCCESS,
                )
                .order_by(LLMRequest.latency_ms)
            ).all()
        ]
        if not latencies:
            return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}

        def percentile(values: list[float], pct: float) -> float:
            index = min(len(values) - 1, int(len(values) * pct))
            return values[index]

        return {
            "p50_ms": percentile(latencies, 0.50),
            "p95_ms": percentile(latencies, 0.95),
            "p99_ms": percentile(latencies, 0.99),
        }

    @staticmethod
    def _since(days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days)
