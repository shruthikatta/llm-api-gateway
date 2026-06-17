# ADR 004: Circuit breaker with automatic failover

## Status

Accepted

## Context

LLM providers fail intermittently. Clients should not implement retry/failover logic per provider.

## Decision

Per-provider circuit breakers in Redis, combined with YAML-configured fallback chains and team-level provider permissions.

## Consequences

- Fast-fail when a provider is unhealthy
- Zero client code changes during outages
- Mid-stream failover is not supported (by design)
