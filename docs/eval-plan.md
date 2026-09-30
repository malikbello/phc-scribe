# Evaluation plan (pre-registration)

**Status:** DRAFT v0, 29 Sept 2026.
- The success thresholds (section 6) are filled in after the 30-item pilot and **frozen before the first training run**.
- The commit that freezes them is recorded here. Later changes need a new, dated section explaining why; the frozen version is never edited.

| Field | Value |
|---|---|
| Frozen at commit | _pending_ |
| Test-set content hash | _pending_ |
| Frozen by | Malik Bello |

## 1. Question
Does fine-tuning N-ATLaS on primary-care documentation improve structured extraction of antenatal visits (Yoruba and English)? Specifically danger-sign detection, versus base N-ATLaS under identical prompting and constrained decoding. Does the improvement survive quantisation to the Q4 artefact we ship?

## 2. Systems compared (baseline ladder)
All rungs use the same schema-constrained decoding and the same grounding/validation pipeline.
1. Rules/keyword baseline (no ML)
2. Llama-3.1-8B-Instruct (N-ATLaS's parent; weights from the ungated mirror `unsloth/Llama-3.1-8B-Instruct`), few-shot
3. Base N-ATLaS, zero-shot
4. Base N-ATLaS, few-shot (**primary comparator**)
5. Fine-tuned N-ATLaS, full precision
6. Fine-tuned N-ATLaS, Q4_K_M GGUF (**primary system: what ships**)

## 3. Test data (PHC-Scribe-Bench v0)
| Stratum | Target size | Source | Counts toward the 500? |
|---|---|---|---|
| S1 English, real notes | ~260 | Real Nigerian clinical notes (African Medical Records candidate, subject to the data audit), de-identified | Yes |
| S3 Yoruba, translated real notes | ~260 | S1 notes translated by a native speaker; clinical meaning checked by the clinical adviser | Yes |
| R Red-team | ~60 | Constructed adversarial cases (negation, hedging, history vs current, third-party symptoms, mixed-language numbers, ASR noise, embedded instructions) | No, reported separately |
| S2 Yoruba, real dictations | later | Health-worker dictations after ethics approval | Acceleration phase |

- **Splits:** group-wise by source note. Translations stay with their originals. Exact and near-duplicate checks run across splits.
- **Enrichment:** at least 30% of test items contain at least one danger sign.
- **Freezing:** the test set is hashed and frozen before any training data is generated.

## 4. Gold labels
- Written annotation guidelines, reviewed by the clinical adviser
- Two annotators label a 60-item overlap set. Cohen's κ is computed per field, with a target ≥ 0.7; the guidelines are revised if below.
- Disagreements are adjudicated by the clinical adviser, and every adjudication is logged

## 5. Metrics
Reported per stratum, per language and per field, each with 95% bootstrap CIs.
- **Primary (safety):** danger-sign recall, where present or possible counts as positive
- **Co-primary:** micro-F1 over (concept, assertion) pairs
- **Secondary:**
  - false-alarm rate
  - ungrounded-field rate
  - numeric exact match (BP, gestational age)
  - schema-valid rate
  - prompt tokens and latency on the laptop CPU (i7-8665U) and on GPU
- **Robustness:** red-team pass rate; scores under simulated ASR noise
- **Regression:** a held-out general Yoruba set, base vs fine-tuned
- **Diacritics:** Yoruba metrics reported with and without tone-mark folding

## 6. Success criteria (pre-registered). Thresholds are fixed at freeze time.
- **P1:** danger-sign recall, fine-tuned Q4 − base few-shot. The lower bound of the 95% paired-bootstrap CI must be > 0, in English **and** in Yoruba.
- **P2:** micro-F1, same test.
- **G1 (guardrail):** false-alarm rate not worse than base by more than **_TBD_** points
- **G2 (guardrail):** general-Yoruba regression within **_TBD_** points
- **Significance of danger-sign detection:** McNemar's test on per-item detection, α = 0.05
- **If any criterion fails, it is reported as failed.** No post-hoc metric switching.

## 7. Analysis hygiene
- Seeds fixed; configs and library versions pinned; every run logged (MLflow) with results JSON committed
- Test data is never used for prompt design, hyperparameters or early stopping. The dev split is used for those.
- The error analysis includes a written taxonomy of failures on a random sample of 50 errors per system
