# ADR-0009: Evaluate the artefact we ship

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Quantisation changes model behaviour. Reporting full-precision scores for a Q4 deployment would overstate quality.

## Decision
The benchmark runs on both the full-precision fine-tune and the Q4_K_M GGUF that runs on the laptop. The Q4 score is the headline result.

## Consequences
Evaluation cost roughly doubles, and the quantisation loss is reported openly.
