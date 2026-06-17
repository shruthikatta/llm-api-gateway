# ADR 001: PostgreSQL for tenancy and usage data

## Status

Accepted

## Context

The gateway needs durable storage for organizations, teams, API keys, model catalog, usage records, and audit logs. Queries are relational (team → keys → usage).

## Decision

Use PostgreSQL with SQLAlchemy ORM and Alembic migrations.

## Consequences

- Strong consistency for usage accounting and audit trails
- Familiar ops story (Cloud SQL in production)
- Firestore deferred to a future multi-region config use case
