# ADR-0012: Tenancy keyed to the Nigeria Health Facility Registry hierarchy

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Permissions, reporting and sync all follow state → LGA → ward → facility.

## Decision
Every row carries a tenant path, and facilities enrol by HFR code.

## Consequences
Enrolment needs a valid HFR code (with a manual fallback for unregistered facilities).
