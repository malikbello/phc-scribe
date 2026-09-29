# ADR-0010: Modular monolith plus separately scaled AI services

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
We have one engineer, an offline single-machine edge node, and clinical records that need one consistent transaction and audit trail.

## Decision
One API service with strict internal modules (records, sync, extraction, rules, reporting, identity, interop), with no cross-module table access. Model serving, ASR workers and the static client run separately. A module is split out only on a trigger: a separate owning team, a sharply divergent load, or a separate security boundary.

## Consequences
Simple to run offline and fast to build. Extraction to services later is a move, not a rewrite.
