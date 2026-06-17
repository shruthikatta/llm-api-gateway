# ADR 005: Dual observability surfaces

## Status

Accepted

## Context

SREs need Prometheus/Grafana metrics; product/admin users need business analytics (cost, usage by team).

## Decision

Expose Prometheus metrics at `/metrics` and build an admin web dashboard backed by Postgres analytics APIs.

## Consequences

- Grafana for operational dashboards (latency, circuits, failover)
- `/dashboard` for budget, usage, and audit visibility
- Slack webhooks for threshold-based alerting
