# S4-W real-speech results (scored 10 Oct 2026, after the stage-2 freeze)

**Secondary set (eval plan §6a): estimates with confidence intervals, no pass/fail.** S4-W is 600 real WazobiaSpeech health clips in Yoruba and Pidgin, at real-world prevalence. 570 are scored; 30 were adjudicated unlabellable at the freeze.

**Method:**
- stratified prediction-powered inference (`scripts/ppi_score.py`, `bench/ppi.py`, ADR-0025);
- committee gold on every item, plus human gold on the seeded random sample (stratum A 60, B 60; 90 labelled after exclusions);
- a cluster bootstrap over speakers within strata (2,000 resamples).

Both systems run the same llama.cpp Q4_K_M runtime and few-shot prompt: the fine-tuned model (run C-fs, the shipped artefact) and base N-ATLaS.

## Labels and freeze
- **Human sample:**
  - 120 of 120 clips labelled (Rahmat all 120; Malik a second label on 36);
  - where both labelled, 25 of 25 agree exactly;
  - **no human label contains any finding**: every labelled clip is "Nothing to record";
  - counts from `scripts/label_report.py`.
- **Settlement:** 11 skip-vs-label disagreements, settled by the **pre-registered clinician rule** (eval plan §6a; guidelines §10.8: the clinician, Rahmat, decides):
  - 10 → unlabellable (excluded);
  - 1 → her label.
  - 30 excluded in total: 8 unintelligible, 5 duplicates, 7 "other", 10 from the settlement.
- **Stage-2 freeze:** 9 Oct, 22:50:57 UTC (`data/bench/test-manifest.json`). The PPI inputs are hashed in `data/bench/s4w.ppi-inputs.json`.
- **Ordering:** model outputs were generated on Modal before the freeze (they do not depend on labels). The automatic report Modal writes was not read until after the freeze. Every number here was computed after it.

## Results: false-alarm rate (a danger sign raised where gold has none)

| Input | Fine-tuned | Base | Fine-tuned − base |
|---|---|---|---|
| Human transcript | **13.2%** [7.8, 19.4] | 26.5% [20.3, 33.6] | **−13.3 points [−15.9, −11.0]** |
| **ASR, fine-tuned (as shipped, ADR-0026, with the H4 loop guard)** | **13.7%** [8.8, 18.9] | 24.3% [19.0, 30.1] | **−10.6 [−13.5, −7.6]** |
| ASR, base N-ATLaS | **15.2%** [9.6, 22.2] | 25.1% [18.2, 33.0] | **−9.9 [−13.5, −6.6]** |

**Fine-tuning cuts false alarms on real Yoruba and Pidgin speech by roughly 40–50%** with every input. Files: `results/s4w/ppi.{transcript,asr-ft,asr-base}.20261009.json`.

**Valid records:** 94.6–96.3% for both systems, in every condition.

**Sensitivity:** counting the 10 settled-as-unlabellable clips as "Nothing to record" (Malik's labels) instead gives a difference of −12.9 [−15.3, −10.7] on transcript input (`results/s4w/ppi.transcript.sensitivity.20261009.json`). The settlement does not change the result.

## What S4-W cannot show (said plainly)
- **Danger-sign recall is not estimable here.** The human sample contains no danger signs, so the PPI recall ratio has a denominator near zero, and the bootstrap values are meaningless (below 0 or above 1). They are in the JSON for completeness and not reported.
  - Recall is measured on S5 (Yoruba, Pidgin) and G (English), where P1 passed in all three languages (`docs/results-frozen-tests.md`).
- **Micro-F1** is uninformative for the same reason (almost no human findings).
- **Safety audit (ADR-0025 §6):** humans found 0 danger signs the committee missed in stratum B. That is 0 of 46 audited clips, an upper 95% bound of 6.3%.
  - The stop is not triggered (it needs at least one miss).
  - With 46 rather than the planned 60 audits, after exclusions, the bound is above the 5% target the plan aimed to certify.
- **Prevalence:** the random sample suggests that real health talk in these clips rarely contains a first-person, current danger sign. This set measures **false alarms on real speech**, the property the nurses asked to protect (G1 tightened to +2 points).

## Laptop hub (non-test pilot items, 10 Oct)
`scripts/hub_check.py` on the reference clinic laptop (Dell Latitude 5400, i7-8665U, 16 GB; Docker given 12 GB), with the shipped models and llama.cpp b11387 (`results/hub/laptop-i7-8665u.json`):

| | |
|---|---|
| First (cold) draft | 408 s |
| Warm draft, p50 / p95 | **124 s** / 230 s |
| Valid | 8 of 8 |
| Danger signs caught | 5 of 6 |
| False alarms | 0 |
