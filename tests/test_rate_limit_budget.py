from __future__ import annotations

import concurrent.futures
from decimal import Decimal
from uuid import uuid4

import pytest

from app.budget.cost import calculate_cost, estimate_cost
from app.budget.service import BudgetService
from app.cache.memory import MemoryCacheClient
from app.exceptions.gateway import BudgetExceededError, RateLimitError
from app.models.llm_model import LLMModel
from app.models.quota import RateLimitPriority, TeamBudget, TeamRateLimit
from app.providers.schemas import ChatMessage, GenerateRequest
from app.rate_limit.service import RateLimitService


class _FakeScalars:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _QuotaFakeDB:
    def __init__(self, *, rate_limit=None, budget=None):
        self.rate_limit = rate_limit
        self.budget = budget

    def scalars(self, statement):
        sql = str(statement)
        if "team_rate_limits" in sql:
            return _FakeScalars(self.rate_limit)
        if "team_budgets" in sql:
            return _FakeScalars(self.budget)
        return _FakeScalars(None)


def _model() -> LLMModel:
    return LLMModel(
        id=uuid4(),
        provider_id=uuid4(),
        name="mock-chat",
        display_name="Mock Chat",
        context_window=8192,
        max_output_tokens=2048,
        input_price_per_million_usd=Decimal("0.50"),
        output_price_per_million_usd=Decimal("1.50"),
        is_active=True,
    )


def test_calculate_cost_from_model_pricing():
    model = _model()
    input_cost, output_cost, total = calculate_cost(
        model,
        prompt_tokens=1000,
        completion_tokens=500,
    )
    assert input_cost == Decimal("0.000500")
    assert output_cost == Decimal("0.000750")
    assert total == Decimal("0.001250")


def test_rate_limit_rejects_burst_requests():
    team_id = uuid4()
    cache = MemoryCacheClient()
    db = _QuotaFakeDB(
        rate_limit=TeamRateLimit(
            team_id=team_id,
            requests_per_minute=2,
            tokens_per_minute=10_000,
            burst_multiplier=1.0,
            priority=RateLimitPriority.NORMAL,
            is_active=True,
        )
    )
    service = RateLimitService(db, cache)  # type: ignore[arg-type]

    service.check_request(team_id)
    service.check_request(team_id)

    with pytest.raises(RateLimitError) as exc_info:
        service.check_request(team_id)

    assert exc_info.value.retry_after is not None
    assert exc_info.value.retry_after >= 1


def test_rate_limit_priority_affects_refill():
    cache = MemoryCacheClient()
    low_team = uuid4()
    high_team = uuid4()
    low = RateLimitService(
        _QuotaFakeDB(
            rate_limit=TeamRateLimit(
                team_id=low_team,
                requests_per_minute=60,
                tokens_per_minute=60,
                burst_multiplier=1.0,
                priority=RateLimitPriority.LOW,
                is_active=True,
            )
        ),
        cache,
    )  # type: ignore[arg-type]
    high = RateLimitService(
        _QuotaFakeDB(
            rate_limit=TeamRateLimit(
                team_id=high_team,
                requests_per_minute=60,
                tokens_per_minute=60,
                burst_multiplier=1.0,
                priority=RateLimitPriority.HIGH,
                is_active=True,
            )
        ),
        cache,
    )  # type: ignore[arg-type]

    low.reserve_tokens(low_team, 30)
    high.reserve_tokens(high_team, 30)

    with pytest.raises(RateLimitError):
        low.reserve_tokens(low_team, 31)

    high.reserve_tokens(high_team, 31)


def test_budget_hard_enforcement_blocks_overspend():
    team_id = uuid4()
    cache = MemoryCacheClient()
    db = _QuotaFakeDB(
        budget=TeamBudget(
            team_id=team_id,
            daily_budget_usd=1.0,
            monthly_budget_usd=10.0,
            warning_threshold_pct=80,
            hard_enforcement=True,
            is_active=True,
        )
    )
    service = BudgetService(db, cache)  # type: ignore[arg-type]

    service.check_and_reserve(team_id, 0.75)
    service.check_and_reserve(team_id, 0.20)

    with pytest.raises(BudgetExceededError) as exc_info:
        service.check_and_reserve(team_id, 0.10)

    assert exc_info.value.period == "daily"


def test_budget_concurrent_reservations_are_atomic():
    team_id = uuid4()
    cache = MemoryCacheClient()
    db = _QuotaFakeDB(
        budget=TeamBudget(
            team_id=team_id,
            daily_budget_usd=1.0,
            monthly_budget_usd=10.0,
            warning_threshold_pct=80,
            hard_enforcement=True,
            is_active=True,
        )
    )

    def attempt() -> bool:
        service = BudgetService(db, cache)  # type: ignore[arg-type]
        try:
            service.check_and_reserve(team_id, 0.40)
            return True
        except BudgetExceededError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: attempt(), range(8)))

    assert sum(results) <= 2


def test_estimate_cost_uses_request_shape():
    model = _model()
    request = GenerateRequest(
        model="mock-chat",
        messages=[ChatMessage(role="user", content="hello world")],
        max_tokens=100,
    )
    cost = estimate_cost(model, request)
    assert cost > Decimal("0")
