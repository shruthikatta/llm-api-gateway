from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

# Request volume and latency
REQUESTS_TOTAL = Counter(
    "gateway_requests_total",
    "Total gateway requests",
    ["endpoint", "status", "provider"],
)
REQUEST_LATENCY_SECONDS = Histogram(
    "gateway_request_latency_seconds",
    "Gateway request latency in seconds",
    ["provider", "model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# Token and cost accounting
TOKENS_TOTAL = Counter(
    "gateway_tokens_total",
    "Total tokens processed",
    ["team_slug", "model", "token_type"],
)
COST_USD_TOTAL = Counter(
    "gateway_cost_usd_total",
    "Total estimated cost in USD",
    ["team_slug", "model"],
)

# Resilience signals
FAILOVER_TOTAL = Counter(
    "gateway_failover_total",
    "Provider failover events",
    ["from_provider", "to_provider"],
)
CIRCUIT_BREAKER_STATE = Gauge(
    "gateway_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
    ["provider"],
)
RATE_LIMITED_TOTAL = Counter(
    "gateway_rate_limited_total",
    "Requests rejected by rate limiting",
    ["team_slug"],
)
BUDGET_EXCEEDED_TOTAL = Counter(
    "gateway_budget_exceeded_total",
    "Requests rejected by budget enforcement",
    ["team_slug"],
)
PROVIDER_ERROR_RATE = Gauge(
    "gateway_provider_error_rate",
    "Rolling provider error rate from health probes",
    ["provider"],
)
PROVIDER_LATENCY_EMA_MS = Gauge(
    "gateway_provider_latency_ema_ms",
    "Rolling provider latency EMA in milliseconds",
    ["provider"],
)

_CIRCUIT_STATE_VALUES = {"closed": 0, "half_open": 1, "open": 2}


def record_circuit_state(provider: str, state: str) -> None:
    CIRCUIT_BREAKER_STATE.labels(provider=provider).set(
        _CIRCUIT_STATE_VALUES.get(state, 0)
    )


def metrics_payload() -> bytes:
    return generate_latest()
