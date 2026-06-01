from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import CacheClient
from app.cache.redis_client import CacheUnavailableError
from app.config.store import get_config_store
from app.exceptions.gateway import RateLimitError
from app.models.quota import RateLimitPriority, TeamRateLimit
from app.providers.schemas import GenerateRequest
from app.rate_limit.token_bucket import (
    PRIORITY_CAPACITY_MULTIPLIER,
    PRIORITY_REFILL_MULTIPLIER,
    RateLimitDecision,
    consume_tokens,
)
from app.telemetry.metrics import RATE_LIMITED_TOTAL

logger = logging.getLogger(__name__)


class RateLimitService:
    """Distributed token-bucket rate limiting backed by Redis."""

    def __init__(self, db: Session, cache: CacheClient):
        self._db = db
        self._cache = cache

    def check_request(self, team_id: uuid.UUID) -> RateLimitDecision:
        config = self._resolve_config(team_id)
        capacity = (
            config.requests_per_minute
            * config.burst_multiplier
            * PRIORITY_CAPACITY_MULTIPLIER[config.priority.value]
        )
        refill = config.requests_per_minute / 60.0
        refill *= PRIORITY_REFILL_MULTIPLIER[config.priority.value]

        key = f"rl:req:{team_id}"
        try:
            decision = consume_tokens(
                self._cache,
                key=key,
                capacity=capacity,
                refill_per_second=refill,
                amount=1.0,
            )
        except CacheUnavailableError:
            logger.error("Rate limit check failed: cache unavailable")
            raise RateLimitError(
                "Rate limiting temporarily unavailable.",
                retry_after=30,
            ) from None

        if not decision.allowed:
            RATE_LIMITED_TOTAL.labels(team_slug=str(team_id)).inc()
            raise RateLimitError(
                "Request rate limit exceeded.",
                retry_after=decision.retry_after_seconds,
                details={
                    "limit_type": "requests_per_minute",
                    "retry_after_seconds": decision.retry_after_seconds,
                },
            )
        return decision

    def reserve_tokens(self, team_id: uuid.UUID, token_count: int) -> None:
        if token_count <= 0:
            return

        config = self._resolve_config(team_id)
        capacity = (
            config.tokens_per_minute
            * config.burst_multiplier
            * PRIORITY_CAPACITY_MULTIPLIER[config.priority.value]
        )
        refill = config.tokens_per_minute / 60.0
        refill *= PRIORITY_REFILL_MULTIPLIER[config.priority.value]

        key = f"rl:tok:{team_id}"
        try:
            decision = consume_tokens(
                self._cache,
                key=key,
                capacity=capacity,
                refill_per_second=refill,
                amount=float(token_count),
            )
        except CacheUnavailableError:
            logger.error("Token rate limit check failed: cache unavailable")
            raise RateLimitError(
                "Rate limiting temporarily unavailable.",
                retry_after=30,
            ) from None

        if not decision.allowed:
            RATE_LIMITED_TOTAL.labels(team_slug=str(team_id)).inc()
            raise RateLimitError(
                "Token rate limit exceeded.",
                retry_after=decision.retry_after_seconds,
                details={
                    "limit_type": "tokens_per_minute",
                    "retry_after_seconds": decision.retry_after_seconds,
                },
            )

    def adjust_tokens(
        self,
        team_id: uuid.UUID,
        *,
        reserved: int,
        actual: int,
    ) -> None:
        delta = actual - reserved
        if delta > 0:
            self.reserve_tokens(team_id, delta)
        elif delta < 0:
            self._refund_tokens(team_id, -delta)

    def _refund_tokens(self, team_id: uuid.UUID, amount: int) -> None:
        if amount <= 0:
            return
        config = self._resolve_config(team_id)
        capacity = (
            config.tokens_per_minute
            * config.burst_multiplier
            * PRIORITY_CAPACITY_MULTIPLIER[config.priority.value]
        )
        refill = config.tokens_per_minute / 60.0
        refill *= PRIORITY_REFILL_MULTIPLIER[config.priority.value]
        key = f"rl:tok:{team_id}"
        try:
            consume_tokens(
                self._cache,
                key=key,
                capacity=capacity,
                refill_per_second=refill,
                amount=-float(amount),
            )
        except CacheUnavailableError:
            logger.warning("Token refund skipped: cache unavailable team=%s", team_id)

    def record_tokens(self, team_id: uuid.UUID, token_count: int) -> None:
        """Post-request token accounting when no prior reservation was made."""
        self.reserve_tokens(team_id, token_count)

    def estimate_request_tokens(self, request: GenerateRequest) -> int:
        prompt_chars = sum(len(message.content) for message in request.messages)
        prompt_tokens = max(1, prompt_chars // 4)
        completion_tokens = request.max_tokens or 1024
        return prompt_tokens + completion_tokens

    def _resolve_config(self, team_id: uuid.UUID) -> TeamRateLimit:
        row = self._db.scalars(
            select(TeamRateLimit).where(
                TeamRateLimit.team_id == team_id,
                TeamRateLimit.is_active.is_(True),
            )
        ).first()
        if row is not None:
            return row

        defaults = get_config_store().get().rate_limit
        return TeamRateLimit(
            team_id=team_id,
            requests_per_minute=defaults.default_requests_per_minute,
            tokens_per_minute=defaults.default_tokens_per_minute,
            burst_multiplier=defaults.default_burst_multiplier,
            priority=RateLimitPriority(defaults.default_priority),
            is_active=True,
        )
