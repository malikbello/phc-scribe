# ADR-0030: Flag a finding whose own quote seems to say the opposite (polarity check)

- **Status:** Proposed (8 Oct 2026). Built and tested; it only adds review notes, so it is safe to serve, but it is not merged for the pilot without Malik's "yes".
- **Date:** 2026-10-08
- **Changes:** the serving pipeline (`/v1/extract`): a new `grounding.checks` list, and `needs_review` is also true when it is not empty. Additive; existing clients keep working. The benchmark, its metrics and the frozen-test verdicts are unchanged.

## Context
Grounding (pipeline step 4) proves that a finding's quote is in the transcript, not that the quote supports the assertion. In the 7 Oct hub run (takada-app `docs/reviews/2026-10-07-pilot-readiness.md`, O1), the shipped model wrote `reduced_fetal_movement: present` with the quote "the baby moves well": a false danger sign that grounding passed.

**Plain negation detection (NegEx-style; Chapman et al. 2001, ConText; Harkema et al. 2009) does not fit these languages.** In Pidgin and Yoruba a symptom is often stated with a negator: "Pikin for my belle no dey move", "I no fit see well", "Ọmọ inú mi kò mì dáadáa". Those are present danger signs. A global negation rule that dropped them would turn false alarms into misses, which the architecture rules out ("false alarms preferred over misses", `docs/architecture.md`).

## Decision
1. **Narrow cues, chosen in advance** (`serve/phc_scribe/polarity.py`), on folded text (no tone marks, lower case):
   - **Normal state**, for the two concepts that are themselves an absence (`reduced_fetal_movement`, `unconscious`): "moves well", "dey kick", "ń mì dáadáa", "alert". These count only when the quote has **no negator**, so "kò mì dáadáa" stays present.
   - **Denial**, for every other concept: the quote opens with a denial ("no", "denies", "nil", "Kò sí", "I no get"), contains "denies"/"negative for", answers a question with "no" ("Any bleeding? No"), or ends "…: nil". Verb negations that state a symptom ("no dey", "no fit", "cannot", "unable") are never a denial.
   - **Scope:** a negation ends at a comma, semicolon, full stop or "but" (annotation guidelines), and every clause of the quote must be a denial. So "bleeding per vaginam; denies gush of fluid" is **not** flagged.
2. **Flag, never drop or change.** A hit adds `{path, reason: "polarity", detail}` to `grounding.checks`, and the finding stays in the record. Danger-sign rules run as before, and the health worker sees the note under "Please check".
3. **Only present / possible / historical are judged.** A false "absent" is a miss, which this check cannot judge from the quote alone.
4. **Developed and measured on non-test data only.** `scripts/polarity_check.py` refuses frozen files (ADR-0022). Results are in `results/polarity/dev.20261008.json`:
   - **Gold findings** (30 pilot items, plus the draft rare-sign phrasebank, which is unapproved and never used for testing):
     - **0 of 78** real present/possible/historical findings flagged (the recall risk);
     - **32 of 40** denial quotes flagged if a model marked them present.
   - **Saved model predictions** on the pilot items (7 runs, 321 non-absent predictions):
     - **7 flags, all 7 wrong by gold**;
     - the shipped model (C-fs) had 2: "vaginal bleeding possible" from "deny gush of fluid", and "leg oedema present" from "swollen ankles: nil".

## Limits (said plainly)
- **The cues were developed on the same dev data they are measured on.** The numbers are an optimistic check, not an estimate. Fresh data decides: the 9 Oct pilot transcripts, and later non-test data.
- **Misses by design:**
  - Yoruba/Pidgin verb negations that deny a symptom ("Belle no dey pain me at all", "I no faint", "Mi ò dákú") are not caught. The same grammar states symptoms ("I no fit see well"), and no safe cue list separates them.
  - **The real fix for those is training data**: the rare-sign phrasebank, once Malik (language) and Rahmat (clinical) approve it (`data/train/phrasebank.rare.v0.yaml`).
- **Pilot data is English clinical-note style.** Conversational and in-language coverage is thin (phrasebank only).

## Consequences
- **What the health worker sees:** a targeted note on the findings most likely to be false alarms. A wrong flag costs a glance; it never removes a finding.
- **What Takada shows:** takada-app adds `grounding.checks` to the draft's "Please check" list (a separate change there).
- **Next:**
  - re-measure on the pilot-day transcripts;
  - if precision stays high, a later ADR may let a high-precision cue lower a flagged finding to "possible" instead of only noting it;
  - never drop on this check alone.
