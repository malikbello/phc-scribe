# ADR-0002: Clinical documentation (structured extraction), not patient Q&A

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Patient-facing health Q&A is crowded: HelpMum's MamaBot-Llama (36k+ maternal Q&A pairs), Ìtọ́jú (equalyz.ai), AISHA, and the "health chatbot in Hausa" example from N-ATLaS launch coverage. Documentation takes about a third of PHC consultation time and about 9 h/month of reporting per worker. No entrant we found does offline, Nigerian-language clinical documentation.

## Decision
The fine-tune turns a visit transcript (Yoruba/English, code-mixed) into a structured encounter record. It never gives advice.

## Consequences
A differentiated wedge that is measurable with exact metrics. Protocol Q&A may come later as a separate module.
