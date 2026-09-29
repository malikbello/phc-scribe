# ADR-0008: Append-only, event-sourced record store with outbox sync

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Records must be auditable, work offline and sync over flaky links.

## Decision
Immutable, content-hashed events (draft, confirmed, amended) with UUIDv7 IDs. An outbox pattern on phone and node, idempotent batched uploads, server watermarks. SQLite at the edge and Postgres in the cloud, sharing one schema.

## Consequences
There are no update-in-place conflicts. Reads require projections.
