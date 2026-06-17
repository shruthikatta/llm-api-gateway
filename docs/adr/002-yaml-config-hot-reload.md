# ADR 002: YAML configuration with hot reload

## Status

Accepted

## Context

Operators need to change routing heuristics, provider enablement, resilience tuning, and alerting thresholds without redeploying.

## Decision

Store behavioral config in `config/gateway.yaml`, validate with Pydantic, reload on interval with rollback on invalid documents.

## Consequences

- Secrets remain in environment / Secret Manager
- Invalid reloads are rejected; last good config is retained
- GitOps-friendly config changes
