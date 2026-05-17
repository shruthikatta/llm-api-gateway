# Phase 1 — Foundation & Gateway Core

## Goal

Ship a production-shaped foundation that can authenticate callers, route models to providers, normalize responses, stream when requested, and run under Docker with observability hooks — without rate limits, budgets, or failover yet.

## Architecture

```
Client
  → FastAPI (/v1/chat/completions)
  → API key auth (Postgres)
  → ModelRouter (DB record → YAML heuristics)
  → ProviderFactory (registry + YAML enablement)
  → BaseProvider adapter (OpenAI | Anthropic | Ollama | Mock)
  → GatewayResponse / SSE StreamChunk
```

Cross-cutting:

- `config/gateway.yaml` → `ConfigStore` (validated Pydantic) + background hot reload
- Structured JSON logging
- OpenTelemetry tracer provider (console or OTLP)
- `CacheClient` protocol → Redis (Docker today, Memorystore later)
- `/live`, `/ready`, `/health`

## Design decisions

| Decision | Choice | Rejected alternative |
|----------|--------|----------------------|
| Tenancy data store | PostgreSQL + SQLAlchemy (already in repo) | Firestore in Phase 1 — would discard working migrations/models |
| Secrets | Environment / Secret Manager later | Secrets in YAML — unsafe and not hot-reload friendly |
| Behavior config | Validated YAML + hot reload | Env-only — poor for routing heuristics and operator edits |
| Provider HTTP | Shared `AsyncHttpClient` (httpx) for Anthropic/Ollama; OpenAI SDK for OpenAI | One mega-SDK — couples adapters and versions |
| Mock provider | In-process, no network | External mock server — slower feedback loop |
| Streaming | SSE OpenAI-compatible chunks | WebSockets — worse client compatibility for chat APIs |
| Redis | Present in Compose + readiness ping via protocol | Defer Redis entirely — harder to introduce Memorystore swap later |

## Tradeoffs

- Sync SQLAlchemy under async routes: acceptable for Phase 1 latency budget with connection pooling; async SQLAlchemy is a Phase 4/5 upgrade if ORM wait time shows in profiles.
- OpenAI keeps the official SDK (rich error types); Anthropic/Ollama use httpx for a thinner, swappable surface.
- Hot reload rejects invalid YAML and keeps the last good config (no partial apply).

## Extensibility

1. Add `providers/<name>/provider.py` implementing `BaseProvider`
2. Register in `PROVIDER_REGISTRY`
3. Add a factory branch (credentials + timeouts)
4. Extend `ProviderType` + Alembic enum value + seed row
5. Add YAML `providers.<name>` and routing heuristics

No API or orchestrator changes required for a well-behaved adapter.

## Run verification checklist

- [x] `pytest` passes
- [x] `/live`, `/ready`, `/health` implemented
- [x] Mock + OpenAI + Anthropic + Ollama adapters
- [x] Streaming and non-streaming chat path
- [x] Docker Compose stack defined
- [x] YAML load + hot reload with rollback-on-invalid
