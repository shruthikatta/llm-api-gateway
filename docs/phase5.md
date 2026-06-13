# Phase 5 — Observability, Analytics & Cloud Deployment

Production observability stack: Prometheus metrics, OpenTelemetry tracing, Grafana dashboards, admin analytics APIs, a web operations console, and Slack alerting.

## What was added

| Area | Implementation |
|------|----------------|
| Prometheus metrics | `app/telemetry/metrics.py` — requests, latency, tokens, cost, failover, circuit breaker, rate limits, budgets |
| Metrics endpoint | `GET /metrics` |
| HTTP middleware | `PrometheusMiddleware` — per-route request counts and latency |
| OpenTelemetry | Existing OTel bootstrap + `gateway.chat` spans with team/model attributes |
| Admin analytics API | `/v1/admin/analytics/*` — overview, timeseries, teams, latency, providers |
| Web dashboard | `GET /dashboard` — operations console (overview, teams/budget, providers, audit, alerts) |
| Slack alerting | `SlackAlertService` — budget warnings, circuit open, high error rate, test alert |
| Grafana | Pre-provisioned dashboard: request rate, latency p95, cost, failover, circuit state |
| Docker stack | `prometheus` + `grafana` services in `docker-compose.yml` |

## Quick start (observability stack)

```bash
docker compose up --build
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000/dashboard | Admin web console |
| http://localhost:8000/metrics | Prometheus scrape target |
| http://localhost:9090 | Prometheus UI |
| http://localhost:3000 | Grafana (`admin` / `admin`) |

Connect the dashboard with your seeded admin API key (from `python -m app.db.seed`).

## Admin analytics endpoints

All require admin role (`Bearer` / `x-api-key`).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/admin/analytics/overview?days=7` | Platform totals, top models |
| GET | `/v1/admin/analytics/timeseries?days=7` | Daily requests, tokens, cost |
| GET | `/v1/admin/analytics/teams?days=7` | Per-team usage breakdown |
| GET | `/v1/admin/analytics/latency?days=7` | p50 / p95 / p99 latency |
| GET | `/v1/admin/analytics/providers` | Provider health + circuit state |
| GET | `/v1/admin/analytics/alerts/config` | Alerting configuration |
| POST | `/v1/admin/analytics/alerts/test` | Send Slack test alert |

## Configuration

### `config/gateway.yaml`

```yaml
alerting:
  enabled: true
  budget_warnings: true
  circuit_open_alerts: true
  error_rate_threshold: 0.5
```

### Environment

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

Set `alerting.enabled: true` and configure the webhook to enable Slack notifications.

## Key metrics

| Metric | Labels | Description |
|--------|--------|-------------|
| `gateway_requests_total` | endpoint, status, provider | Request volume |
| `gateway_request_latency_seconds` | provider, model | End-to-end latency histogram |
| `gateway_tokens_total` | team_slug, model, token_type | Token accounting |
| `gateway_cost_usd_total` | team_slug, model | Estimated spend |
| `gateway_failover_total` | from_provider, to_provider | Automatic failover events |
| `gateway_circuit_breaker_state` | provider | 0=closed, 1=half_open, 2=open |
| `gateway_rate_limited_total` | team_slug | Rate limit rejections |
| `gateway_budget_exceeded_total` | team_slug | Budget rejections |
| `gateway_provider_error_rate` | provider | Rolling error rate from probes |
| `gateway_provider_latency_ema_ms` | provider | Rolling latency EMA |

## Architecture

```
Client request
    → PrometheusMiddleware (HTTP metrics)
    → OpenTelemetry span (gateway.chat)
    → GatewayService (business metrics on success/failure)
    → ResilientLLMService → CircuitBreakerService (circuit metrics + alerts)
    → Health probes → provider error/latency gauges + alerts
```

## Cloud deployment (outline)

Phase 5 includes deployment scaffolding for Google Cloud Run:

- **Cloud Logging** — JSON structured logs via `JsonFormatter`
- **Cloud Monitoring** — scrape `/metrics` or use Managed Prometheus
- **Secret Manager** — `SLACK_WEBHOOK_URL`, provider API keys
- **Firestore** — optional config store for multi-region (future)

See `deploy/cloudrun/` and `.github/workflows/deploy.yml` for CI/CD templates.

## Design decisions

- **Prometheus over custom metrics DB** — industry standard, integrates with Grafana and Cloud Monitoring.
- **Dual dashboards** — Grafana for SRE/metrics; web console for admin/business analytics from Postgres.
- **Fail-open alerting** — Slack failures are logged but never block gateway requests.
- **Team slug in business metrics, team ID in enforcement metrics** — slug for human-readable dashboards; ID where DB lookup is expensive.

## Tests

```bash
pytest tests/test_observability.py tests/test_analytics.py -q
```
