# Evaluation plan (pre-registration)

**Status:** **Stage 1 (items) frozen 4 Oct 2026, 00:53 UTC** (§6a criteria; Malik: "if the freeze is the next blocker do it"). Stage 2 (labels) follows the S4-W labelling. Drafted 29 Sept 2026.
- The success thresholds (section 6) are filled in after the 30-item pilot and **frozen before the first training run**.
- The commit that freezes them is recorded here. Later changes need a new, dated section explaining why; the frozen version is never edited.

| Field | Value |
|---|---|
| Frozen at commit | stage 1: the commit that adds `data/bench/test-manifest.json` (`git log -- data/bench/test-manifest.json`) |
| Test-set content hash | sha256 of `data/bench/test-manifest.json`: `6b19315761a43f2e5ce9646d1c49730f75125a2d04c4870afc7a03f077430d50` (5 files, 1,690 items: G 300, H 454, S5 300, R 36, S4-W 600) |
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
Revised by ADR-0016 (accepted 30 Sept) and ADR-0018 (accepted 1 Oct; in use from 4 Oct because MAMAI access is still pending). The original plan (real AMR notes, S1/S3) failed the data audit (`docs/data-audit.md`).

| Stratum | Target size | Source | Counts toward the 500? |
|---|---|---|---|
| **S4** real patient speech | ≥ 500 | NigBench-MAMAI test split, Yoruba + Pidgin (ADR-0016), labelled in the review app. Two inputs: human transcript; audio through N-ATLaS ASR | **Yes** |
| S4-W (fallback, only if MAMAI is refused by 5 Oct; **in use from 4 Oct**, ADR-0018 accepted) | ≥ 500 | WazobiaSpeech `dev` + `dev_test` health clips (corrected 4 Oct, audit M5), Yoruba + Pidgin, enriched + random groups (ADR-0018) | Yes, instead of S4 |
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
    - **Measured 3 Oct (Kaggle, 30 pilot items; `results/checks-asrft/`):**
      - with 1.12: danger-sign recall **0.80** and **29/30** schema-valid;
      - without it (1 Oct): recall 0.60 and 24/30 valid.
      - **Rule met: the primary base comparator, and the fine-tuned model, decode with repetition penalty 1.12.** The 1.0 run is reported as supplementary.
- **If any criterion fails, it is reported as failed.** No post-hoc metric switching.

## 6a. Amendment, 4 Oct 2026 (before the stage-1 freeze; pre-freeze audit C1–C3, H1)
Why: `docs/audit/2026-10-04-pre-freeze-audit.md`.
- The real-speech set S4-W has about 2.5% danger-sign prevalence (P1 untestable).
- §1 and P1 named English and Yoruba, but the counted real speech is Yoruba and Pidgin.
- The comparison runtime was unspecified.
- §4 contradicted ADR-0025.

This section replaces those parts of §1, §3, §4 and §6. Nothing has been trained or scored on any test item.

**Question (§1):** does fine-tuning N-ATLaS improve structured antenatal extraction, above all danger-sign detection, in **Yoruba, Nigerian Pidgin and English**, versus base N-ATLaS, and does the improvement survive quantisation to the Q4 artefact we ship?

**What each test set measures:**

| Set | Items | Language | Danger-sign items | Gold | Measures |
|---|---|---|---|---|---|
| **S5** constructed patient statements (new; `bench/constructed.py`) | 300 | 150 yo, 150 pcm | 78 + 78 | By construction (lexicon clause = evidence) | **P1** (yo, pcm), P2 |
| **G** generated ANC notes | 300 | en | 226 | By construction | **P1** (en), P2, vitals and GA |
| **S4-W** real health speech | 600 | 300 yo, 300 pcm | ≈15 (real-world prevalence) | ADR-0025: committee, random human sample, stratified PPI | **Secondary:** real-speech false alarms, micro-F1, recall; the ASR-input condition |
| **H** hard negatives (real antenatal teaching) | 454 | en, yo, pcm | 0 | No finding (source) | **G1** (pass/fail) |

The ≥30% enrichment rule applies to the P1 sets (S5 52%, G 75%). S4-W keeps real-world prevalence on purpose: it is the false-alarm and real-speech test.

**S5 construction:**
- Written by the assistant from a fixed lexicon, independently of every compared or trained model (N-ATLaS, Llama-3.1) and of the labelling committee.
- First-person clauses by a pregnant woman, following the annotation guidelines (present / denied / hedged / past; severity cues).
- 18% general talk with nothing to record; seed 20261011.
- **The draft rare-sign phrase bank is not used for training** while S5 is a test set (same author and style).

**Primary and guardrail criteria (replace §6 P1, P2, G1; G2 unchanged):**
- **P1:** danger-sign recall, fine-tuned Q4 − base few-shot. The lower bound of the 95% paired-bootstrap CI must be > 0 **in each of Yoruba (S5), Pidgin (S5) and English (G)**. A language that fails is reported as failed.
- **P2:** micro-F1, same test, on S5 (yo, pcm) and G (en).
- **G1:** the upper bound of the 95% paired-bootstrap CI of the false-alarm-rate difference (fine-tuned − base) must be ≤ **+2 points** on **H** (454 real-speech sentences, gold = no finding by source; no labelling needed).
- **Secondary (reported with PPI CIs, no pass/fail):** S4-W real speech, with transcript input and with ASR input (base and fine-tuned ASR). Covers false-alarm rate, micro-F1 and recall (few positives).
- **Label budget (4 Oct, before any label):** S4-W carries no pass/fail criterion, so its human sample is 60 from stratum A + 60 from B (the B audit stays at 60, the smallest number that certifies a miss rate below 5% with no misses), 30% double-labelled (36 clips: Rahmat 18, Success 18, each paired with Malik's label).

**Runtimes (C3):**
- **Base few-shot (primary comparator):** HF transformers, fp16, xgrammar constrained decoding.
- **Fine-tuned Q4 (primary system):** llama.cpp with the same prompt, the same JSON schema as a grammar, greedy decoding, repetition penalty 1.12 over the whole context (`repeat_last_n` = the 8,192-token server context, matching HF; the chat endpoint rejects −1).
- **The 2×2 is reported:** base and fine-tuned, each in HF fp16 and in llama.cpp Q4. The fine-tuning effect and the quantisation/runtime effect are then visible separately.

**Other strata (audit H5, M2):**
- **MamaBench and AMR are dropped:** there is not enough time to map their answers to the record schema safely.
- **R (red team)** is a small constructed set (negation scope, hedging, third parties, past vs current, embedded instructions, mixed-language numbers), reported separately.
- **Tone marks (§5 "with and without folding"):** the metrics compare concepts and assertions, not text, so tone marks affect only evidence grounding. Grounding accepts tone-folded quotes, and the number of folded matches is reported per system.

**Gold labels (replaces §4):**
- **S4-W:** ADR-0025. The committee labels every clip; humans label a seeded random sample within strata, blind to the committee. Cohen's κ comes from the double-labelled 20%; the estimates and CIs from stratified PPI (`bench/ppi.py`, pre-registered with its tests). Malik is the main labeller; Rahmat double-labels and settles clinical disagreements.
- **S5 and G:** by construction.
- **H:** no finding, by source.

## 7. Analysis hygiene
- Seeds fixed; configs and library versions pinned; every run's results JSON committed with its config and code version (git). MLflow is not used (corrected 4 Oct, audit M1)
- Test data is never used for prompt design, hyperparameters or early stopping. The dev split is used for those.
- The error analysis includes a written taxonomy of failures on a random sample of 50 errors per system
