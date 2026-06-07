from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.exceptions.base import GatewayError
from app.retry.policy import RetryPolicy, compute_backoff_delay

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryBudgetExhausted(GatewayError):
    status_code = 429
    error_type = "retry_budget_exhausted"
    retryable = False


class RetryExecutor:
    """Retry retryable failures with exponential backoff and a per-request budget."""

    def __init__(self, policy: RetryPolicy | None = None):
        self._policy = policy or RetryPolicy.from_config()

    async def run(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        label: str,
        budget: int | None = None,
    ) -> T:
        policy = self._policy
        remaining_budget = budget if budget is not None else policy.retry_budget
        attempt = 0
        last_error: GatewayError | None = None

        while True:
            try:
                return await operation()
            except GatewayError as exc:
                last_error = exc
                if not exc.retryable:
                    raise
                if attempt >= policy.max_retries or remaining_budget <= 0:
                    if remaining_budget <= 0:
                        raise RetryBudgetExhausted(
                            f"Retry budget exhausted for {label}.",
                            details={"label": label, "attempts": attempt},
                        ) from exc
                    raise

                delay = compute_backoff_delay(attempt, policy)
                attempt += 1
                remaining_budget -= 1
                logger.info(
                    "Retrying %s attempt=%s delay=%.3fs error=%s",
                    label,
                    attempt,
                    delay,
                    exc.message,
                )
                await asyncio.sleep(delay)

        raise last_error  # pragma: no cover
