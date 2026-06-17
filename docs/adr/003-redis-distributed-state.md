# ADR 003: Redis for distributed gateway state

## Status

Accepted

## Context

Multiple gateway replicas need shared rate limit buckets, budget counters, and circuit breaker state.

## Decision

Use Redis with Lua scripts for atomic token-bucket and circuit breaker operations. Abstract behind `CacheClient` protocol.

## Consequences

- Correct behavior under concurrent load
- Memorystore drop-in for Cloud Run production
- Fail-open paths when Redis is temporarily unavailable
