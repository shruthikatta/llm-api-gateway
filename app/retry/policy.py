from __future__ import annotations

import random
from dataclasses import dataclass

from app.config.store import get_config_store


@dataclass(slots=True, frozen=True)
class RetryPolicy:
    max_retries: int
    base_delay_ms: float
    max_delay_ms: float
    retry_budget: int

    @classmethod
    def from_config(cls) -> RetryPolicy:
        section = get_config_store().get().resilience
        return cls(
            max_retries=section.max_retries,
            base_delay_ms=section.retry_base_delay_ms,
            max_delay_ms=section.retry_max_delay_ms,
            retry_budget=section.retry_budget,
        )


def compute_backoff_delay(attempt: int, policy: RetryPolicy) -> float:
    """Exponential backoff with full jitter, in seconds."""
    exp = min(policy.max_delay_ms, policy.base_delay_ms * (2**attempt))
    return random.uniform(0, exp) / 1000.0
