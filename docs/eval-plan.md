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
Revised by ADR-0016 (accepted 30 Sept) and ADR-0018 (proposed 30 Sept). The original plan (real AMR notes, S1/S3) failed the data audit (`docs/data-audit.md`).

| Stratum | Target size | Source | Counts toward the 500? |
|---|---|---|---|
| **S4** real patient speech | ≥ 500 | NigBench-MAMAI test split, Yoruba + Pidgin (ADR-0016), labelled in the review app. Two inputs: human transcript; audio through N-ATLaS ASR | **Yes** |
| S4-W (fallback, only if MAMAI is refused by 5 Oct) | ≥ 500 | WazobiaSpeech `dev_test` health clips, Yoruba + Pidgin, enriched + random groups (ADR-0018) | Yes, instead of S4 |
| G generated ANC notes | 300 | `data/bench/g.20261002.jsonl`; tests vitals, gestational age and the rules engine | No, reported separately, labelled "generated" |
| MamaBench ANC slice | 78 | HelpMum MamaBench, clinician-authored vignettes (CC-BY-4.0) | No, reported separately |
| AMR | 62 | African Medical Records, synthesized OCR/HTR documents | No, reported separately |
| U Uyo antenatal records | 538 | Real hospital records (St Luke's, Uyo; OSF, CC-BY-4.0): structured vitals, symptom and diagnosis; tests the **rules engine** against clinician diagnoses (ADR-0019) | No, reported separately |
| H hard negatives | 454 | Real antenatal teaching (Ajagbe 2024, MIT): sentences in en 148 / yo 158 / pcm 148, gold = no finding (ADR-0020). Measures false findings and false flags | No, reported separately |
| R red-team | ~60 | Constructed adversarial cases (negation, hedging, history vs current, third-party symptoms, mixed-language numbers, ASR noise, embedded instructions) | No, reported separately |
| **G2 general-Yoruba set** | 900 | Belebele `yor_Latn` test (CC-BY-SA-4.0), `facebook/belebele` @ `7899cdf`; chosen by Malik 1 Oct | Guardrail only (§6 G2) |

- **Splits:** group-wise by source note. Translations stay with their originals. Exact and near-duplicate checks run across splits.
- **Enrichment:** at least 30% of test items contain at least one danger sign.
- **Freezing (ADR-0022, two stages):**
  - **Stage 1 (items):** the test items (ids, speakers, text) are hashed before any training data is built.
  - **Stage 2 (labels):** the adjudicated gold labels are hashed before any fine-tuned model is scored.
  - Exclusions at stage 2 are declared and reported.
  - Each stage is one commit, recorded here.

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
- **G1 (guardrail):** false-alarm rate not worse than base by more than **2** points (tightened from 5 on 3 Oct; see below)
- **G2 (guardrail):** general-Yoruba regression within **_TBD_** points, measured on Belebele `yor_Latn` (900 items, 4-way multiple choice; set chosen by Malik 1 Oct; scoring proposed as accuracy by answer log-likelihood, to confirm at the freeze; margin set from the pilot)
- **Significance of danger-sign detection:** McNemar's test on per-item detection, α = 0.05

**Margins approved by Malik, 1 Oct; proposals A–E approved the same day** (frozen with the test set; evidence in `docs/research/finetuning-review.md`):
- **G1:** the upper bound of the 95% paired-bootstrap CI of *false-alarm rate (fine-tuned − base few-shot)* must be **≤ +2 points** (tightened from +5; see the G1 decision below). Base few-shot false-alarm rate was 0.385 [0.125, 0.667] on the 30 pilot items and 0.187 [0.127, 0.250] on G; Llama-3.1 few-shot reached 0.000 and 0.020. The pilot is too small to set the margin from its variance, so 5 points is a clinical judgement: a fine-tuned model may not add more than about one extra false referral per 20 visits.
- **G2:** the lower bound of the 95% paired-bootstrap CI of *Belebele `yor_Latn` accuracy (fine-tuned − base)* must be **≥ −m**, where **m = min(3 points, 50% of N-ATLaS's accuracy gain over Llama-3.1-8B-Instruct)** (proposal E: the FDA-style fixed-margin rule keeps at least half of the reference model's advantage; the 3-point cap is the margin Malik approved). If N-ATLaS is *not* better than Llama-3.1 on Belebele, m = 3 points. **Measured 1 Oct (pre-freeze run): N-ATLaS 42.78%, Llama-3.1-8B-Instruct 34.44% on 900 items; gain 8.3 points, half = 4.2, so m = 3 points.** Scoring: zero-shot, next-token likelihood of the option letters A–D (`bench/belebele.py`), same prompt for every model. Both base scores come from the pre-freeze Kaggle run.
- **G1 decision (3 Oct, before the freeze):** both nurses who completed the clinical sign-off (Rahmat and Success) rejected the +5-point tolerance as too loose for antenatal care, where each false alarm is an unnecessary referral a mother may pay to travel for. Malik approved tightening it to **+2 points** on 3 Oct. The original +5 rationale is kept above for the record.
- **Supplementary comparator (proposal B, reported, not a pass/fail criterion):** base N-ATLaS few-shot with unconstrained generation then JSON extraction (`--unconstrained`), so the base model is also shown without the forced-JSON handicap. **Measured 1 Oct on the 30 pilot items:** unconstrained N-ATLaS few-shot is *worse* (10/30 valid, most failures are schema violations; recall 0.40), so constrained decoding helps the base model and the primary comparator is the more generous one.
- **Decoding cap:** the base comparator keeps `max_new_tokens = 768`. The pilot ran N-ATLaS few-shot at 768 and 1536: every metric was identical (6/30 invalid in both; failed outputs simply ran on to the new cap, up to 5,052 characters), so the cap is not the cause and raising it would only add compute.
- **List bounds in the decoding schema (added 2 Oct, before the freeze; ADR-0024):**
  - `findings`, `anc.tests` and `anc.medications` are capped at 10 items each, in the schema every system decodes against (`decoding_schema()`). The cap applies to the base comparator and the fine-tuned model alike.
  - The largest real gold record has 5 findings, so the cap never cuts a genuine answer; it stops a loop from repeating an item until the token cap.
  - The baseline and pilot numbers above were decoded without it. The final comparison re-scores the base model under the bounded schema, so both sides are decoded identically.
- **Repetition penalty for the base comparator (added 3 Oct, before the freeze and before the result):**
  - The N-ATLaS model card's usage example sets `repetition_penalty = 1.12`. Our base runs used greedy decoding without it, so a reviewer could say the base model was not run as its makers intend.
  - The pre-freeze `checks` run scores base N-ATLaS few-shot with 1.12 on the 30 pilot (dev) items.
  - **Rule:**
    - The primary base comparator uses 1.12 if, on the pilot items, its danger-sign recall is at least as high as without it and its schema-valid count is no lower. Otherwise it stays at 1.0.
    - Either way, the other setting is reported as a supplementary comparator, and the fine-tuned model is decoded with the same setting as the primary comparator.
    - This follows the principle above: the base model gets the more generous comparator.
- **If any criterion fails, it is reported as failed.** No post-hoc metric switching.

## 7. Analysis hygiene
- Seeds fixed; configs and library versions pinned; every run logged (MLflow) with results JSON committed
- Test data is never used for prompt design, hyperparameters or early stopping. The dev split is used for those.
- The error analysis includes a written taxonomy of failures on a random sample of 50 errors per system
