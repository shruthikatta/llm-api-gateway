# LLM API Gateway — Engineering Case Study

## Problem statement

Teams integrating LLM capabilities face repeated infrastructure work: multiple provider SDKs, inconsistent APIs, no centralized auth, unpredictable costs, and fragile production behavior when providers degrade. Each application reinvents routing, rate limiting, and observability.

The LLM API Gateway solves this by providing a **unified, OpenAI-compatible API** with multi-tenant auth, policy enforcement, budget controls, automatic failover, and production observability — deployable to Google Cloud Run.

## Architecture

A FastAPI gateway sits between clients and LLM providers:

- **PostgreSQL** — organizations, teams, API keys, models, usage records, audit logs
- **Redis** — distributed rate limits, budget counters, circuit breaker state
- **Provider adapters** — OpenAI, Anthropic, Ollama, Mock (normalized to one response schema)
- **YAML config** — hot-reloadable routing heuristics, resilience tuning, alerting thresholds

See [architecture.md](architecture.md) for diagrams.

## Scalability decisions

| Decision | Rationale |
|----------|-----------|
| Stateless gateway on Cloud Run | Horizontal scale; Redis/Postgres hold shared state |
| Redis token buckets | O(1) rate limit checks at high concurrency |
| Atomic budget counters | Prevent overspend races across replicas |
| Provider abstraction | Add providers without API changes |
| Mock provider for testing | Validate gateway scale independent of external APIs |

Load testing demonstrates **5000+ concurrent requests** against the mock provider with sub-second p95 latency on typical dev hardware.

## Reliability features

- **Circuit breakers** per provider (closed → open → half-open)
- **Automatic failover** via configured fallback chains
- **Retries with exponential backoff** and retry budgets
- **Background health probes** with rolling error-rate windows
- **Graceful degradation** — fail-open circuit breaker when Redis unavailable

Chaos and fault-injection scripts validate recovery without client code changes.

## Tradeoffs

| Choice | Benefit | Cost |
|--------|---------|------|
| Sync SQLAlchemy in async routes | Simpler ORM, existing migrations | May need async DB later at extreme scale |
| YAML hot reload | Operator-friendly config | Invalid YAML rejected (safe but requires discipline) |
| OpenAI-compatible API | Easy client migration | Some provider-specific features not exposed |
| Dual dashboards (Grafana + web) | SRE metrics + business analytics | Two surfaces to maintain |
| Budget fail-hard (402) | Clear spend enforcement | Clients must handle 402 distinctly from 429 |

## Performance results

Reference benchmarks (mock provider, local Docker):

- **~200–600 req/s** at 200 concurrent connections (5000 request batch)
- **p95 latency < 250 ms** for non-streaming chat
- **200 concurrent SSE streams** without connection exhaustion

Prometheus metrics expose request rate, latency histograms, failover counts, and circuit breaker state for continuous monitoring.

## Lessons learned

1. **Normalize early** — a stable response schema pays off when adding providers.
2. **Separate secrets from behavior** — env/Secret Manager for keys; YAML for routing and limits.
3. **Test resilience explicitly** — chaos scripts caught failover edge cases unit tests missed.
4. **Instrument at the gateway** — provider latency alone doesn't explain end-to-end user experience.
5. **Mock provider is essential** — enables CI, load tests, and local demos without API spend.

## What's next

- Async SQLAlchemy for DB-bound workloads
- Firestore config store for multi-region
- Embeddings API surface
- Per-model routing policies and A/B testing
