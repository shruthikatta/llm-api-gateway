# LLM API Gateway

Cloud-native LLM gateway: unified API, authentication, multi-provider routing, and production foundation for rate limiting, budgets, and resilience in later phases.

## Phase status

- **Phase 1** — Foundation & gateway core: complete
- **Phase 2** — Teams, permissions, policies, admin APIs: complete (OpenAI-first)
- **Phase 3** — Rate limiting, budgets, usage accounting, audit logs: complete
- **Phase 4** — Circuit breakers, retries, failover, health probes: complete
- **Phase 5** — Observability, analytics dashboards, Grafana, Slack alerts: complete
- **Phase 6** — Integration tests, load testing, benchmarks, documentation: complete

See [docs/phase1.md](docs/phase1.md) through [docs/phase6.md](docs/phase6.md). Portfolio case study: [docs/case-study.md](docs/case-study.md).

## Quick start

### 1. Local dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
# set OPENAI_API_KEY / ANTHROPIC_API_KEY as needed
```

### 2. Infrastructure

```bash
docker compose up -d postgres redis
alembic upgrade head
python -m app.db.seed
```

### 3. Run the gateway

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Full stack via Docker

```bash
docker compose up --build
```

Includes Prometheus (`:9090`), Grafana (`:3000`, admin/admin), and the admin dashboard at `/dashboard`.

## API

| Endpoint | Purpose |
|----------|---------|
| `GET /live` | Liveness (process up) |
| `GET /ready` | Readiness (DB + Redis) |
| `GET /health` | Aggregate health |
| `GET /metrics` | Prometheus metrics |
| `GET /dashboard` | Admin web console |
| `POST /v1/chat/completions` | Unified chat (Bearer / `x-api-key`) |
| `GET /v1/providers` | List providers |
| `GET /v1/models` | List models |
| `GET /v1/me` | Current authenticated user |
| `GET/POST /v1/admin/teams` | Admin: list/create teams |
| `PUT /v1/admin/teams/{id}/policy` | Admin: update prompts/filters/routing |
| `GET/PUT /v1/admin/teams/{id}/rate-limit` | Admin: team rate limits |
| `GET/PUT /v1/admin/teams/{id}/budget` | Admin: team budgets |
| `GET /v1/admin/teams/{id}/budget/dashboard` | Admin: budget dashboard |
| `GET /v1/admin/teams/{id}/usage` | Admin: usage summary |
| `GET /v1/admin/audit-logs` | Admin: audit trail |
| `GET /v1/admin/analytics/overview` | Admin: platform analytics |
| `GET /v1/admin/analytics/timeseries` | Admin: usage time series |
| `GET /v1/admin/analytics/providers` | Admin: provider health analytics |
| `POST /v1/admin/analytics/alerts/test` | Admin: test Slack alert |
| `POST /v1/admin/config/reload` | Admin: force YAML config reload |

### Example (Mock provider — no external API key)

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <seeded-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mock-chat",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

### Streaming

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <seeded-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mock-chat",
    "stream": true,
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

## Configuration

- Secrets / env: `.env.local` (see `.env.example`)
- Behavior: `config/gateway.yaml` (hot-reloaded; invalid reloads are rejected)

## Tests

```bash
pytest -q
```

### Load & performance (optional, requires running gateway)

```bash
pip install -r requirements-dev.txt
export GATEWAY_API_KEY=<seeded-key>

python scripts/load_test_phase6.py --requests 5000 --concurrency 200
python scripts/benchmark_phase6.py --requests 500 --concurrency 50
python scripts/stream_stress_phase6.py --streams 200
locust -f locustfile.py --host http://localhost:8000
```

### Demo

```bash
chmod +x scripts/demo.sh
export GATEWAY_API_KEY=<seeded-key>
./scripts/demo.sh
```

## Architecture

- [docs/architecture.md](docs/architecture.md) — system diagrams
- [docs/api.md](docs/api.md) — API reference
- [docs/case-study.md](docs/case-study.md) — engineering case study
- [docs/adr/](docs/adr/) — architecture decision records
