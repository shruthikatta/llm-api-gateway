# Phase 2 — Auth, Routing & Policy Enforcement

## Scope

OpenAI-first operation for day-to-day use. The policy and permission layers are
**provider-agnostic** so Anthropic/Ollama/etc. can be enabled later by granting
team permissions — no orchestrator rewrite.

## What was added

| Capability | Implementation |
|------------|----------------|
| Teams | `Team` under `Organization`; API keys bind to a team |
| Provider permissions | `TeamProviderPermission` allow/deny |
| Allowed models | `TeamAllowedModel` allow-list (empty = deny all) |
| Routing policies | `TeamPolicy.routing_config` (aliases, preferred provider) |
| System / compliance prompts | Injected ahead of client messages |
| Content filters | Input block + optional output redact/block |
| Request enrichment | Metadata (`team_id`, request id, client `user`) |
| Admin APIs | `/v1/admin/teams/...`, `/v1/admin/config/reload` |
| Config reload | YAML hot-reload + admin force reload |

## Request pipeline

```
API key → active team
  → routing aliases
  → input content filter
  → system + compliance prompt injection
  → ModelRouter
  → model + provider allow-lists
  → enrichment metadata
  → provider (OpenAI today)
  → output filter
  → GatewayResponse / SSE
```

## Admin endpoints (require `admin` role)

| Method | Path |
|--------|------|
| POST | `/v1/admin/config/reload` |
| GET/POST | `/v1/admin/teams` |
| GET | `/v1/admin/teams/{id}` |
| GET/PUT | `/v1/admin/teams/{id}/providers` |
| GET/PUT | `/v1/admin/teams/{id}/models` |
| GET/PUT | `/v1/admin/teams/{id}/policy` |

## Enabling another provider later

1. Activate the provider row (`is_active=true`)
2. `PUT /v1/admin/teams/{id}/providers` with that `provider_id`
3. `PUT /v1/admin/teams/{id}/models` to include that provider's models
4. Optionally set `routing_config.preferred_provider`

No changes required in `GatewayService` or chat routes.

## Seed defaults

- Team `platform` — OpenAI + Mock allowed
- Anthropic/Ollama catalog rows exist but inactive / not granted
- Policy includes sample system + compliance prompts, alias `gpt-4` → `gpt-4.1-mini`
