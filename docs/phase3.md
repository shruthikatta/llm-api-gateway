# Phase 3 — Rate Limiting, Budget Enforcement & Admin Controls

## Scope

Distributed rate limiting (Redis token buckets), per-team budgets with atomic enforcement, usage accounting, audit logs, and admin dashboards.

## What was added

| Capability | Implementation |
|------------|----------------|
| Request rate limits | `RateLimitService` — Redis token bucket per team (`requests/minute`) |
| Token rate limits | Reserved pre-request, reconciled post-response (`tokens/minute`) |
| Priority tiers | `low` / `normal` / `high` refill multipliers (0.5× / 1× / 2×) |
| Burst handling | Configurable `burst_multiplier` on capacity |
| Retry-After | `RateLimitError` + `Retry-After` response header |
| Daily/monthly budgets | `BudgetService` — atomic Redis counters + DB fallback |
| Cost calculation | Model `input_price_per_million_usd` / `output_price_per_million_usd` |
| Usage accounting | `LLMRequest` + `UsageRecord` written on every successful chat |
| Audit logs | `AuditLog` model + admin mutation hooks |
| Budget dashboard | `GET /v1/admin/teams/{id}/budget/dashboard` |
| Usage summary | `GET /v1/admin/teams/{id}/usage` |

## Request pipeline (Phase 3)

```
API key → team/policy/routing (Phase 2)
  → request rate limit check
  → token reservation (estimated)
  → budget reservation (estimated cost)
  → provider call
  → usage persistence
  → token/budget reconciliation (actual vs estimate)
  → response
```

## Admin endpoints (require `admin` role)

| Method | Path |
|--------|------|
| GET/PUT | `/v1/admin/teams/{id}/rate-limit` |
| GET/PUT | `/v1/admin/teams/{id}/budget` |
| GET | `/v1/admin/teams/{id}/budget/dashboard` |
| GET | `/v1/admin/teams/{id}/usage` |
| GET | `/v1/admin/audit-logs` |

## Configuration (`config/gateway.yaml`)

```yaml
rate_limit:
  default_requests_per_minute: 60
  default_tokens_per_minute: 100000
  default_burst_multiplier: 2.0
  default_priority: normal

budget:
  default_daily_budget_usd: 100.0
  default_monthly_budget_usd: 1000.0
  default_warning_threshold_pct: 80
  default_hard_enforcement: true
```

Teams without explicit `team_rate_limits` / `team_budgets` rows inherit these defaults.

## Edge cases

| Scenario | Behavior |
|----------|----------|
| Redis unavailable (rate limit) | Fail closed — `429` with `retry_after=30` |
| Redis unavailable (budget) | Fall back to DB spend totals |
| Concurrent spending | Lua `INCRBYFLOAT` with limit check |
| Budget race | Atomic reservation before provider call |
| Gateway restart | Redis TTL keys expire; DB is source of truth for dashboards |
| Multiple replicas | Shared Redis counters coordinate limits |

## Tradeoffs

- **Token reservation uses estimates** — actual usage reconciled after response; large deltas may briefly exceed soft limits.
- **Streaming usage is estimated** — token counts derived from content length when providers omit usage in stream.
- **402 for budget exceeded** — distinguishes spend limits from provider `429` rate limits.

## Load testing

```bash
python scripts/load_test_phase3.py
```

Runs concurrent requests against the mock provider to validate rate-limit rejection under burst traffic.
