# ADR-0001: Enter NAIC 2026 under PS3 (Sectoral Fine-Tuning)

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
NAIC 2026 has three problem statements, and a team may enter only one. "Primary healthcare and community health" is a named PS3 domain. PS3 is validated with a 500+ example benchmark against base N-ATLaS. PS2 (Voice-First Access) targets citizens who don't type, requires the hosted official ASR service, and requires 50+ documented real-user interactions.

## Decision
Enter PS3 with a primary-healthcare fine-tune of N-ATLaS, delivered through a documented API.

## Consequences
Validation depends on a real-data benchmark we control, not on arranging field access in 10 days. A field pilot follows in the acceleration phase (25 Oct–4 Nov) as extra evidence. The fine-tuned model is an N-ATLaS derivative, so it carries the N-ATLaS terms.
