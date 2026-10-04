# Frozen-test results (4 Oct 2026)

Pre-registered in `docs/eval-plan.md` §6 and §6a before the stage-1 freeze (manifest sha256 `6b193157…`). Selected model: **run C-fs** (`natlas-qlora-v1-weighted-fs`, chosen on dev and pilot only). Every number below is from the frozen items, scored once.

**Systems:**
- **Primary system (shipped):** fine-tuned, merged, imatrix Q4_K_M, llama.cpp.
- **Primary comparator:** base N-ATLaS few-shot, HF fp16, batch 1.
- Both decode greedily, with repetition penalty 1.12, under the same JSON-schema constraint.

**Reproduce:** `python scripts/final_scores.py --items <G+S5+H+R> --base results/frozen/base/frozen.pred.jsonl --ft-q4 results/frozen/natlas-qlora-v1-weighted-fs-q4/frozen.pred.jsonl --ft-hf results/frozen/natlas-qlora-v1-weighted-fs/frozen-b8.pred.jsonl --base-q4 results/frozen/base-q4/frozen.pred.jsonl --out results/final/verdicts.json`

## Verdicts: all pass

Each verdict compares the fine-tuned Q4 model with the base HF model (fine-tuned minus base), as a 95% paired bootstrap interval.

| Test | Set | Base | Fine-tuned Q4 | Difference [95% CI] | Rule | Verdict |
|---|---|---|---|---|---|---|
| **P1** danger-sign recall | S5 Yoruba (78 danger items) | 52.6% | 67.9% | +15.4 [+4.8, +26.4] | low > 0 | **pass** |
| | S5 Pidgin (78) | 68.0% | 76.9% | +9.0 [+1.3, +17.2] | low > 0 | **pass** |
| | G English (226) | 80.2% | 91.0% | +10.7 [+4.0, +17.6] | low > 0 | **pass** |
| **P2** micro-F1 | S5 Yoruba | 0.261 | 0.365 | +10.4 [+3.7, +17.7] | low > 0 | **pass** |
| | S5 Pidgin | 0.476 | 0.575 | +9.9 [+4.7, +15.0] | low > 0 | **pass** |
| | G English | 0.471 | 0.685 | +21.4 [+17.0, +25.7] | low > 0 | **pass** |
| **G1** false alarms | H (454 real antenatal-teaching sentences, no finding) | 15.9% | 9.3% | −6.6 [−10.8, −2.7] | high ≤ +2 | **pass** |
| **G2** general Yoruba | Belebele yor_Latn (900) | 42.9% | 42.2% (HF) | −0.7 [−2.1, +0.8] | low ≥ −3 | **pass** |

**Exact McNemar test** (item-level danger detection; supplementary): Yoruba 16 vs 4 items, p = 0.012; Pidgin 9 vs 2, p = 0.065; English 26 vs 9, p = 0.006.

## The 2×2 (fine-tuning × runtime)
**Danger-sign recall** (false-alarm rate in brackets):

| Set | Base HF | Base Q4 | Fine-tuned HF | Fine-tuned Q4 |
|---|---|---|---|---|
| S5 yo | 52.6% (47.2%) | 52.6% (58.3%) | 67.9% (9.7%) | 67.9% (12.5%) |
| S5 pcm | 68.0% (45.8%) | 68.0% (47.2%) | 79.5% (33.3%) | 76.9% (29.2%) |
| G en | 80.2% (25.3%) | 81.4% (18.0%) | 88.7% (24.0%) | 91.0% (26.7%) |
| H | – (15.9%) | – (26.9%) | – (11.2%) | – (9.3%) |

- The fine-tuning effect is large in every set.
- Quantisation to Q4 costs little: F1 on S5 yo 0.403 (HF) → 0.365 (Q4); on G 0.718 → 0.685.

## Checks beyond the pre-registration (post hoc; reported, not used for verdicts)

**G1 grouping.** H items carry one group per language, so the pre-registered cluster bootstrap resamples only 3 clusters. With an item-level bootstrap the result is −6.6 [−9.9, −3.5]. False alarms fall in every language:
- English 8.1% → 5.4%;
- Yoruba 22.8% → 16.5%;
- Pidgin 16.2% → 5.4%.

**Schema-invalid outputs on H.** The metric scores an invalid output as "no flag", which favours the system with more invalid outputs: fine-tuned Q4 has 33 of 454 invalid, base HF 12 of 454. Sensitivity (`results/final/g1-sensitivity.json`):

| View | Fine-tuned Q4 − base HF | G1 |
|---|---|---|
| As registered | −6.6 [−9.9, −3.5] | pass |
| Worst case: every invalid output counted as a false alarm, for both systems | −2.0 [−6.0, +1.98] | pass (barely) |
| Repaired: the invalid parts dropped and the record re-parsed | −6.4 [−9.7, −3.3] | pass |

The commonest cause (29 errors across the 35 invalid fine-tuned outputs, all sets) is one cross-field rule the grammar cannot express: a lab test named without a result. Repair recovers 30 of 33 on H, and those recovered records rarely flag danger.

**Product follow-up (post-freeze, does not change these results):** a deterministic salvage step in the serving pipeline that drops incomplete test and medication entries and duplicate findings, instead of rejecting the record. It is validated on dev and pilot only.

**R (red team, 36 items; reported, no criterion):** no improvement. Recall is 81.3% for base and 75.0% for fine-tuned Q4 (−6.3 [−26.3, +15.4]). False alarms are 57.1% and 47.6%. It is too small to separate the systems; the errors go into the taxonomy.

## Not yet scored
**S4-W** (600 real WazobiaSpeech clips): secondary, PPI estimates after the stage-2 label freeze (ADR-0025).
