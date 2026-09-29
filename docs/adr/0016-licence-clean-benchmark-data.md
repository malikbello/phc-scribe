# ADR-0016: Benchmark data is team-authored and licence-clean, anchored in open real data

- **Status:** Proposed (awaiting Malik)
- **Date:** 2026-09-29
- **Changes:** `docs/eval-plan.md` §3 (test data strata). The plan is still a draft (thresholds not frozen), so this is a pre-freeze revision, recorded here and in the plan.

## Context
- The data audit (`docs/data-audit.md` §4) applied the pre-registered rules and found the planned S1 source unusable. AMR has 62 synthesized records, about 1 ANC note, and none with danger signs.
- The survey (`docs/data-sources-survey.md`) found **no public corpus of real Nigerian ANC notes**. Real notes are held by hospitals and teams (Iyàwó, HelpMum, UCH). Getting them before 12 Oct needs a data-use agreement plus NDPA/ethics clearance. It is uncertain and not in our control.
- Many of the open African clinical conversation and QA sets are **CC-BY-NC-SA**. We can evaluate on them. We should not train a product we may commercialise (Track B) on them.
- What *is* open and licence-clean:
  - **MamaBench** (HelpMum, CC-BY-4.0): 434 clinician-authored maternal and child vignettes, about 80 ANC and 37 ANC with danger signs.
  - **NigBench-MAMAI** (Intron, CC-BY-4.0, consented, gated; access pending): 20k *real* maternal-health utterances from Nigerian women, including 4,082 in Yoruba and 3,490 in Pidgin.
  - **IyàwóBench** (CC-BY-4.0): 200 febrile-illness triage vignettes from Nigerian PHCs, with a structured vitals format.
  - **AMR** (CC-BY-4.0): shows real Nigerian note style.
- Precedent: Intron's AfriSpeech-Dialog (NAACL 2025) and med-convo-nig built peer-reviewed benchmarks from **clinician-authored OSCE-style patient cards**, not patient records.

## Decision
1. **We author the core benchmark ourselves**, so we own it and can release it (CC-BY-4.0). This is the planned acceleration-phase contribution, brought forward.
   - **S1, English ANC visit notes (~260, counted):** the nurse and the medical student write them from structured **case cards**, in real PHC style (shorthand such as `G3P2`, `32/40`, `BP 150/100`, `c/o`, `TCA 2/52`; style reference: AMR).
   - Case cards are seeded from:
     - MamaBench maternal cases (CC-BY, attributed)
     - the WHO ANC DAK danger-sign list and Standing Orders scenarios
     - Nigerian distributions for age, parity and gestational age (St Luke's MNCH, if its licence allows; otherwise NDHS summary tables)
   - At least 30% of items carry a danger sign. Negation, history-vs-current and third-party cases are included on purpose.
   - **S3, Yoruba (~260, counted):** Malik (native speaker) renders each S1 note as a Yoruba dictation, as planned. The nurse checks clinical meaning.
2. **Real-language stratum S4 (counted if access arrives; target ≥ 200):** NigBench-MAMAI **test-split transcripts** (Yoruba, Pidgin; real, consented, CC-BY). Task: extract patient-reported findings with assertion status and danger-sign flags. This is documentation of what the patient says, consistent with ADR-0002; we never answer the question. It is reported as its own stratum, because vitals are absent.
3. **Not counted; reported separately:** R red-team (unchanged); AMR (62) as an out-of-domain real-style slice; NC-licensed conversation sets (med-convo-nig, afrispeech-dialog) as an optional conversation → note slice, **evaluation only**.
4. **Licence firewall:**
   - Training data comes only from CC-BY sources and our own writing.
   - NC-licensed data never enters training.
   - Every source is listed with its revision and licence in `docs/license-ledger.md`.
5. **Integrity rules:**
   - **No LLM writes any test item or gold label.** Rules and keyword pre-annotation is allowed; a human confirms every label.
   - Training data *may* include LLM-drafted notes that a clinician reviews. They must come from different case cards than the test set, and we disclose this.
   - Splits are grouped by case-card seed (a MamaBench pair never spans splits).
   - 20% of test items are double-annotated, and agreement (Cohen's κ per field) is reported.
   - The report states plainly: "clinician-authored from case cards, not patient records."
6. **Real clinical data remains upside, not a dependency.** We contact Iyàwó and HelpMum about evaluation-only access. Anything that arrives becomes an extra reported stratum and never replaces the pre-registered ones.

## Consequences
- The benchmark no longer depends on third-party permission, ethics timelines or NC licences. It is buildable in time with our own effort.
- **Effort (estimate):**
  - S1: about 520 items × roughly 10 minutes (card, note, gold label) ≈ 85–90 person-hours.
  - S3: about 17 h.
  - Double annotation: about 10 h.
  - About 5–6 days for three people at around 5 h/day. **This depends on the nurse and the student confirming now.**
  - Minimum viable version: 300 S1 + 260 S3.
- Weakness, stated openly: S1 and S3 are realistic but authored, not observed. S4 gives real patient language, and the AMR slice gives real-style notes, to show that performance transfers.
- The authored ANC corpus plus the gold schema is itself a submission contribution: the first open Yoruba/English ANC documentation benchmark.
- Supersedes the S1 source line of `docs/eval-plan.md` §3 once accepted. ADR-0013 is unchanged: ANC scope holds, because we author the ANC coverage we need.
