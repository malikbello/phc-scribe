# ADR-0004: Schema-constrained decoding plus evidence grounding

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
LLMs produce malformed JSON and invent fields. Clinical records must be traceable.

## Decision
Decode against the encounter JSON schema (llama.cpp grammar / vLLM guided decoding). Every non-null field carries an evidence span that is machine-verified against the transcript. Ungrounded or out-of-range fields are dropped, and the record is marked NEEDS_REVIEW.

## Consequences
The hallucination rate becomes a measurable metric. Recall on implicit facts may drop slightly, which we accept for safety.
