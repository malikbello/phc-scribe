# ADR-0016: The counted benchmark is real, consented, CC-BY speech data; generated notes are a labelled supplement

- **Status:** Proposed (awaiting Malik)
- **Date:** 2026-09-29 (revised the same day, after reading the NAIC build requirements)
- **Changes:** `docs/eval-plan.md` §3 (test data strata). The plan is still a draft with no thresholds frozen, so this is a pre-freeze revision, recorded here and in the plan.

## Context
- **NAIC rules** (`docs/naic-requirements.md`): PS3 validation is a "benchmark of 500+ examples vs base N-ATLaS". Real-world validation means "testing with actual users, real data or live benchmarks. **Not simulated or hypothetical results.**" Sector specialists sit on the panel.
- **The planned S1 source is unusable.** The data audit found AMR has 62 synthesized records and about 1 ANC note.
- **Real Nigerian ANC notes are not published anywhere.** Getting them needs third-party agreements plus NDPA/ethics clearance. That will not happen by 12 Oct.
- **The team's time is limited.** The nurse and the student cannot commit long hours. Malik is the only reliable annotator. So labelling must be cheap per item.
- **NigBench-MAMAI** ("Voices for Smart Care", Intron Health, **CC-BY-4.0**, access requested):
  - 20,489 **real** recordings of Nigerian women, mainly rural and peri-urban, describing maternal and reproductive health concerns in their own words.
  - Manually transcribed; informed consent stated; PII removed.
  - Test split: Yoruba 432, Pidgin 365, Hausa 353, Igbo 297, and more. Train split: about 18k.
- **MamaBench** (HelpMum, CC-BY-4.0, accessible): 434 clinician-authored maternal and child vignettes; 78 ANC.

## Decision
1. **Counted benchmark: S4, real patient speech (≥ 500 items).**
   - Source: NigBench-MAMAI **test-split** utterances in Yoruba and Pidgin (plus English if present), sampled at random with a fixed seed, stratified by language.
   - Task (consistent with ADR-0002): document what the woman reports, i.e. findings from the ANC vocabulary with assertion status, verbatim evidence and danger-sign flags. We never answer her question.
   - Items with no ANC finding stay in; they measure false alarms.
   - Two input conditions: **(a)** the human transcript; **(b)** the real audio through **N-ATLaS ASR**, then the model (end-to-end, real voice).
2. **Labelling that fits the team's time.**
   - Malik labels with a local, offline tool (`tools/labeler/`, about 1 minute per item). Evidence spans are chosen by text selection, so they are verbatim by construction.
   - Keyword hints can be shown but are never pre-ticked.
   - **The nurse double-labels a random 50 items (about 1 hour).** Cohen's κ per concept and assertion is reported. She adjudicates disagreements on danger signs only.
   - Written guidance: `docs/annotation-guidelines.md`, extended for patient speech.
3. **Supplementary strata, reported separately and not counted toward the 500.**
   - **G, generated ANC visit notes:** records are built first, then rendered to clinic shorthand by templates or an open model of a different family from N-ATLaS, then automatically verified (every gold value is quoted verbatim; the rules engine reproduces the flags).
     - Purpose: to test vitals, gestational age and the rules engine, which patient speech rarely contains.
     - Labelled "generated" in every table.
   - **MamaBench ANC slice** (clinician-authored).
   - **AMR** (62, real-style handwritten transcriptions).
   - **R**, the red-team set.
   - Optional **NC** conversation sets (evaluation only).
4. **Training data.**
   - The NigBench-MAMAI **train** split (real, CC-BY), with labels from Malik plus rule pre-annotation, disclosed.
   - Generated notes from case cards disjoint from all test sources.
   - **No test utterance, speaker or case card appears in training.** MAMAI splits are already speaker-disjoint.
   - NC-licensed data never enters training.
5. **Real clinical notes are upside only.** We contact Iyàwó and HelpMum about evaluation-only access. Anything that arrives becomes an additional reported stratum.
6. **Fallback if MAMAI access has not arrived by 2 Oct:**
   - Email Intron Health directly.
   - Meanwhile build S4 tooling and the G stratum.
   - If there is still no access by 5 Oct, the counted benchmark becomes MamaBench (434, clinician-authored) plus G, and the report states plainly that it is **not** real patient data.

## Consequences
- The counted 500 are real, consented and licence-clean. That meets "real data … not simulated" and keeps the Track B product path open (CC-BY allows commercial use with attribution).
- Human cost: Malik about 9–10 h of labelling for 500 items; the nurse about 1 h (agreement) plus about 1.5 h (rule review). Nothing depends on the nurse's or the student's longer availability.
- **Scope shift, stated openly.** Our input moves from what a health worker writes to what the pregnant woman says: the history part of an ANC visit. Vitals and labs are tested in stratum G, and the report says so.
- The end-to-end speech condition uses N-ATLaS ASR and the LLM together, which strengthens integration (criterion 2).
- **Dependency:** Intron's approval. It is mitigated by the fallback above.
