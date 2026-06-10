# Phase 4 — Resilience & High Availability

## Scope

Production-grade failure handling: circuit breakers, retries with backoff, provider health probes, automatic failover, and chaos simulation — with zero client API changes.

## What was added

| Capability | Implementation |
|------------|----------------|
| Circuit breakers | `CircuitBreakerService` — Redis Lua state machine (closed → open → half-open) |
| Retries | `RetryExecutor` — exponential backoff + jitter, per-request retry budget |
| Timeouts | `asyncio.wait_for` / `asyncio.timeout` in `ResilientLLMService` |
| Health probes | Background `run_health_probes()` worker in app lifespan |
| Rolling metrics | `ProviderHealthStore` — latency EMA + error rate per provider |
| Failover routing | `build_route_chain()` — YAML `fallback_chains` + team `fallback_providers` |
| Graceful failover | `GatewayService._generate_with_failover()` tries routes in order |
| Reservation rollback | Token/budget reservations released on total failure |
| Chaos simulation | Mock provider `chaos_fail_rate` / `chaos_always_fail` |
| Extended `/health` | Per-provider health, latency EMA, error rate, circuit state |

## Request pipeline (Phase 4)

```
_prepare → rate limits + budget reservation
  → for each route in fallback chain:
      → circuit breaker allow?
      → retry loop (backoff, budget)
      → provider call (timeout)
      → on success: record health + return
      → on retryable failure: next route
  → on total failure: release reservations
```

## Configuration (`config/gateway.yaml`)

```yaml
routing:
  fallback_chains:
    - prefixes: ["gpt", "o1"]
      providers: [openai, mock]
      fallback_model: mock-chat

resilience:
  request_timeout_seconds: 60
  max_retries: 2
  retry_base_delay_ms: 50
  retry_max_delay_ms: 2000
  retry_budget: 3
  health_probe_interval_seconds: 30
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_seconds: 30
    half_open_max_calls: 2
    rolling_window_seconds: 60

providers:
  mock:
    chaos_fail_rate: 0.0
    chaos_always_fail: false
```

Team policy override:

```json
{
  "routing_config": {
    "fallback_providers": ["mock"]
  }
}
```

## Circuit breaker transitions

| State | Behavior |
|-------|----------|
| **Closed** | Normal traffic; failures counted |
| **Open** | Fast-fail with `CircuitOpenError`; triggers failover |
| **Half-open** | Limited probe calls after `recovery_timeout_seconds` |
| **Recovery** | Successful probe closes circuit |

## Edge cases

| Scenario | Behavior |
|----------|----------|
| Primary provider outage | Automatic failover to next allowed route |
| Circuit open | Skip provider, try fallback immediately |
| Retry storm | `retry_budget` caps total retry attempts per request |
| Rate limit interaction | Reservations rolled back on failure; not double-charged |
| Stream failure before chunks | Failover to next provider (no mid-stream switch) |
| Redis unavailable (CB) | Fail open — allow requests |

## Chaos testing

```bash
# Toggle mock chaos in gateway.yaml, then:
python scripts/chaos_test_phase4.py
```

Demonstrates outage → circuit open → failover → recovery without client changes.

## Tradeoffs

- **No mid-stream failover** — once bytes are delivered, the request stays on that provider.
- **Fail-open circuit breaker** when Redis is down — favors availability over isolation.
- **Estimated streaming usage** — same as Phase 3; provider usage preferred when available.
