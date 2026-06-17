# Architecture

End-to-end architecture of the LLM API Gateway across all six phases.

## System context

```mermaid
flowchart TB
    Client[Client Apps / SDKs]
    Dashboard[Admin Dashboard /dashboard]
    Grafana[Grafana]
    Prometheus[Prometheus]
    Slack[Slack Webhooks]

    subgraph Gateway["LLM API Gateway (FastAPI)"]
        Auth[API Key Auth]
        Router[Model Router]
        Policies[Policy Engine]
        RateLimit[Rate Limiter]
        Budget[Budget Enforcer]
        Resilience[Circuit Breaker + Retry]
        Providers[Provider Adapters]
        Metrics[Prometheus Metrics]
        Analytics[Analytics Service]
    end

    Postgres[(PostgreSQL)]
    Redis[(Redis)]
    OpenAI[OpenAI API]
    Anthropic[Anthropic API]
    Ollama[Ollama]
    Mock[Mock Provider]

    Client --> Auth
    Dashboard --> Auth
    Auth --> Router
    Router --> Policies
    Policies --> RateLimit
    RateLimit --> Budget
    Budget --> Resilience
    Resilience --> Providers
    Providers --> OpenAI
    Providers --> Anthropic
    Providers --> Ollama
    Providers --> Mock

    Auth --> Postgres
    Router --> Postgres
    RateLimit --> Redis
    Budget --> Redis
    Resilience --> Redis
    Analytics --> Postgres

    Metrics --> Prometheus
    Prometheus --> Grafana
    Gateway --> Slack
```

## Request sequence (non-streaming)

```mermaid
sequenceDiagram
    participant C as Client
    participant G as Gateway
    participant A as Auth
    participant P as Policy
    participant R as Rate/Budget
    participant CB as Circuit Breaker
    participant PR as Provider

    C->>G: POST /v1/chat/completions
    G->>A: Validate API key
    A->>G: User + Team
    G->>P: Apply routing, prompts, filters
    G->>R: Check rate limit + budget
    G->>CB: Allow provider?
    CB->>PR: generate()
    alt Provider fails (retryable)
        PR-->>G: Error
        G->>CB: Record failure
        G->>PR: Fallback provider
    end
    PR-->>G: Response
    G->>G: Normalize + account usage
    G-->>C: GatewayResponse
```

## Deployment topology

```mermaid
flowchart LR
    subgraph GCP["Google Cloud (production)"]
        CR[Cloud Run]
        SM[Secret Manager]
        CL[Cloud Logging]
        CM[Cloud Monitoring]
        SQL[(Cloud SQL)]
        MR[(Memorystore Redis)]
    end

    LB[Load Balancer / Ingress]
    LB --> CR
    CR --> SQL
    CR --> MR
    CR --> SM
    CR --> CL
    CR --> CM
```

## Component map

| Layer | Components |
|-------|------------|
| API | FastAPI routers, SSE streaming, admin APIs |
| Auth | API keys, roles (admin/developer/viewer), team scoping |
| Routing | DB model registry + YAML heuristics + fallback chains |
| Policy | System prompts, content filters, routing preferences |
| Quota | Redis token buckets, atomic budget counters |
| Resilience | Circuit breakers, retries, health probes, failover |
| Observability | Prometheus, OTel, Grafana, admin dashboard, Slack |
| Data | PostgreSQL (tenancy, usage, audit), Redis (distributed state) |

## Phase evolution

| Phase | Focus |
|-------|-------|
| 1 | Gateway core, providers, normalization |
| 2 | Auth, teams, policies, admin APIs |
| 3 | Rate limits, budgets, audit logs |
| 4 | Circuit breakers, retries, failover |
| 5 | Metrics, analytics, dashboards, alerts |
| 6 | Integration tests, load testing, documentation |

See individual phase docs: [phase1.md](phase1.md) through [phase6.md](phase6.md).
