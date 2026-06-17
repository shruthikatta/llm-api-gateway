# API Reference

Base URL: `http://localhost:8000` (development)

Authentication: `Authorization: Bearer <api-key>` or `x-api-key: <api-key>`

## Health & ops

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/live` | No | Process liveness |
| GET | `/ready` | No | DB + Redis readiness |
| GET | `/health` | No | Aggregate health + provider status |
| GET | `/metrics` | No | Prometheus metrics |
| GET | `/dashboard` | No | Admin web console (UI) |

## Chat

### POST `/v1/chat/completions`

OpenAI-compatible chat completion endpoint.

**Request body:**

```json
{
  "model": "mock-chat",
  "messages": [{"role": "user", "content": "hello"}],
  "stream": false,
  "temperature": 1.0,
  "max_tokens": 1024
}
```

**Response (200):**

```json
{
  "id": "mock-abc123",
  "object": "chat.completion",
  "provider": "mock",
  "model": "mock-chat",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "mock-response: hello"},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 5,
    "total_tokens": 15
  },
  "latency_ms": 12.5
}
```

**Streaming:** Set `"stream": true`. Response is SSE (`text/event-stream`).

**Error codes:**

| Code | Meaning |
|------|---------|
| 401 | Invalid/missing API key |
| 402 | Budget exceeded |
| 403 | Permission denied (team/model/provider) |
| 429 | Rate limited (`Retry-After` header) |
| 502 | Provider error (may have exhausted fallbacks) |
| 504 | Timeout |

## Discovery

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/providers` | Yes | List providers |
| GET | `/v1/models` | Yes | List models |
| GET | `/v1/me` | Yes | Current user + team |

## Admin (requires admin role)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/v1/admin/teams` | List/create teams |
| GET/PUT | `/v1/admin/teams/{id}/policy` | Team policy |
| GET/PUT | `/v1/admin/teams/{id}/rate-limit` | Rate limits |
| GET/PUT | `/v1/admin/teams/{id}/budget` | Budgets |
| GET | `/v1/admin/teams/{id}/budget/dashboard` | Budget dashboard |
| GET | `/v1/admin/teams/{id}/usage` | Usage summary |
| GET | `/v1/admin/audit-logs` | Audit trail |
| POST | `/v1/admin/config/reload` | Force YAML reload |
| GET | `/v1/admin/analytics/overview` | Platform analytics |
| GET | `/v1/admin/analytics/timeseries` | Daily usage series |
| GET | `/v1/admin/analytics/teams` | Per-team analytics |
| GET | `/v1/admin/analytics/latency` | Latency percentiles |
| GET | `/v1/admin/analytics/providers` | Provider health |
| POST | `/v1/admin/analytics/alerts/test` | Test Slack alert |

## Error format

```json
{
  "error": {
    "type": "rate_limit_error",
    "message": "Request rate limit exceeded.",
    "details": {"retry_after_seconds": 12}
  }
}
```

Interactive docs: `GET /docs` (Swagger UI).
