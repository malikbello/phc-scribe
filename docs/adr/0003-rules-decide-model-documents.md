# ADR-0003: Deterministic rules decide danger signs; the model only documents

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Small on-device generators cannot be both helpful and safe as clinicians (MAM-AI, Zanzibar 2026). Clinical decisions must be auditable and cite national protocol.

## Decision
Danger-sign flags and referral prompts come from a versioned rules engine (YAML). Each rule cites its National Standing Orders / WHO ANC source and has nurse-reviewed tests. The model's output feeds the rules, and the worker can also tap danger signs directly, with no AI in the path.

## Consequences
Safety doesn't depend on model quality or latency. Rules must be maintained and reviewed per module.
