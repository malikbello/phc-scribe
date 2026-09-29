# ADR-0013: Antenatal care is clinical module one

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
PS3 requires one clearly defined domain. A 500-item benchmark spread across all of primary care would be statistically meaningless. ANC danger signs are a finite, reviewable list with WHO DAK logic, and Nigeria carries 28.7% of global maternal deaths.

## Decision
Module one is ANC visit documentation plus danger signs. Later modules (fever/IMCI, immunisation, family planning, general OPD, PPMV) each add their own schema, rules, benchmark and LoRA adapter. Fallback: if the data audit finds few ANC notes, use a general PHC encounter core plus the ANC danger-sign module.

## Consequences
Narrow proof now, a platform story for scale.
