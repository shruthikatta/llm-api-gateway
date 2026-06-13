from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.services.analytics_service import AnalyticsService


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def one(self):
        return self._rows[0]


class _FakeDB:
    def __init__(self):
        self.team_id = uuid4()
        self.team = type(
            "Team",
            (),
            {"id": self.team_id, "slug": "platform", "is_active": True},
        )()
        self._execute_calls = 0

    def scalars(self, statement):
        sql = str(statement).lower()
        if "teams" in sql:
            return type("R", (), {"all": lambda _: [self.team]})()
        if "latency_ms" in sql:
            return type("R", (), {"all": lambda _: [120.0, 250.0, 400.0]})()
        return type("R", (), {"all": lambda _: []})()

    def execute(self, statement):
        sql = str(statement).lower()
        self._execute_calls += 1
        if "date_trunc" in sql and "llm_requests" in sql:
            return _Rows([(datetime.now(timezone.utc), 5, 1000, 300.0)])
        if "date_trunc" in sql and "usage_records" in sql:
            return _Rows([(datetime.now(timezone.utc), Decimal("0.05"))])
        if "llm_requests" in sql and "teams" in sql:
            return _Rows([(self.team_id, "platform", 5, 1000, 300.0, 0)])
        if "usage_records" in sql and "api_keys" in sql:
            return _Rows([(self.team_id, Decimal("0.05"))])
        if "group_by" in sql:
            return _Rows([("mock-chat", 5, Decimal("0.05"))])
        return _Rows([(5, 4, 1000, 300.0)])

    def scalar(self, statement):
        return Decimal("0.05")


def test_platform_overview_with_fake_db():
    overview = AnalyticsService(_FakeDB()).platform_overview(days=7)  # type: ignore[arg-type]
    assert overview.team_count == 1
    assert overview.request_count == 5
    assert overview.success_count == 4
    assert float(overview.total_cost_usd) == 0.05


def test_timeseries_with_fake_db():
    points = AnalyticsService(_FakeDB()).timeseries(days=7)  # type: ignore[arg-type]
    assert len(points) == 1
    assert points[0].request_count == 5


def test_team_breakdown_with_fake_db():
    teams = AnalyticsService(_FakeDB()).team_breakdown(days=7)  # type: ignore[arg-type]
    assert teams[0].team_slug == "platform"
    assert teams[0].request_count == 5


def test_latency_percentiles_with_fake_db():
    percentiles = AnalyticsService(_FakeDB()).latency_percentiles(days=7)  # type: ignore[arg-type]
    assert percentiles["p50_ms"] >= 0
    assert percentiles["p95_ms"] >= percentiles["p50_ms"]
