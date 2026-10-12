# PHC Scribe benchmark report

**Question (pre-registered, `docs/eval-plan.md` §1 and §6a):** does fine-tuning N-ATLaS improve structured antenatal extraction, above all danger-sign detection, in **Yorùbá, Nigerian Pidgin and English**, against base N-ATLaS? And does the improvement survive quantisation to the 4-bit model that ships?

**Answer:** yes. All four pre-registered tests pass. On 570 real health speech clips, fine-tuning halves false alarms. The shipped 4-bit model keeps the gains.

## 1. How the test was kept honest
- **Pre-registration:** the metrics, thresholds and test sets were written down before any fine-tuned model was scored (`docs/eval-plan.md`). The false-alarm margin was tightened from +5 to **+2 points** on 3 Oct, at the nurses' request, before the freeze.
- **Two-stage freeze (ADR-0022):**
  - the test items were hashed before any training data was built;
  - the gold labels were hashed before any fine-tuned model was scored (`data/bench/test-manifest.json`).
- **Scored once:** no choice (model, prompt, quantisation, threshold) was made on a test set. The model was chosen on dev (127 items) and pilot (30) data only (ADR-0024).
- **Fair comparator:** base N-ATLaS with the same few-shot prompt, the same JSON schema, and the repetition penalty its model card recommends (1.12).
- **Statistics:** 95% paired bootstrap intervals clustered by source group, plus McNemar's test on per-item danger detection.

## 2. Test sets
| Set | Items | Language | Real or constructed | Measures |
|---|---|---|---|---|
| **S5** patient statements | 300 (156 with a danger sign) | Yorùbá, Pidgin | Constructed from a fixed lexicon, independent of every model compared | P1 recall, P2 F1 |
| **G** antenatal notes | 300 (226 with a danger sign) | English | Generated | P1, P2 |
| **H** hard negatives | 454 | en 148, yo 158, pcm 148 | **Real** antenatal teaching sentences (Ajagbe 2024, MIT) | G1 false alarms |
| **S4-W** health speech | 600 (570 scored) | Yorùbá, Pidgin | **Real** WazobiaSpeech clips (CC-BY-4.0) | False alarms on real speech; text and speech-recognition input |
| **Belebele** `yor_Latn` | 900 | Yorùbá | Real | G2: general Yorùbá kept |
| **R** red team | 36 | mixed | Constructed adversarial cases | Reported only |

**Why constructed sets carry recall:** in real speech only about 2.5% of clips contain a danger sign, too few to measure recall. S5 and G make every danger sign frequent enough to test. The real sets carry the false-alarm tests the nurses asked to protect.

## 3. Pre-registered verdicts: all pass
Fine-tuned Q4 (shipped) minus base N-ATLaS; `docs/results-frozen-tests.md`, `results/final/verdicts.json`.

| Test | Set | Base | Fine-tuned Q4 | Difference [95% CI] | Rule | Verdict |
|---|---|---|---|---|---|---|
| **P1** danger-sign recall | S5 Yorùbá | 52.6% | 67.9% | +15.4 [+4.8, +26.4] | low > 0 | **pass** |
| | S5 Pidgin | 68.0% | 76.9% | +9.0 [+1.3, +17.2] | low > 0 | **pass** |
| | G English | 80.2% | 91.0% | +10.7 [+4.0, +17.6] | low > 0 | **pass** |
| **P2** micro-F1 | S5 Yorùbá | 0.261 | 0.365 | +10.4 [+3.7, +17.7] | low > 0 | **pass** |
| | S5 Pidgin | 0.476 | 0.575 | +9.9 [+4.7, +15.0] | low > 0 | **pass** |
| | G English | 0.471 | 0.685 | +21.4 [+17.0, +25.7] | low > 0 | **pass** |
| **G1** false alarms | H (454 real sentences) | 15.9% | 9.3% | −6.6 [−10.8, −2.7] | high ≤ +2 | **pass** |
| **G2** general Yorùbá | Belebele (900) | 42.9% | 42.2% | −0.7 [−2.1, +0.8] | low ≥ −3 | **pass** |

**McNemar** (items where only one system caught the danger sign):
- Yorùbá: 16 against 4, p = 0.012;
- Pidgin: 9 against 2, p = 0.065;
- English: 26 against 9, p = 0.006.

## 4. Does it survive 4-bit quantisation? (the 2×2)
Danger-sign recall, with the false-alarm rate in brackets:

| Set | Base fp16 | Base Q4 | Fine-tuned fp16 | **Fine-tuned Q4 (ships)** |
|---|---|---|---|---|
| S5 Yorùbá | 52.6% (47.2%) | 52.6% (58.3%) | 67.9% (9.7%) | **67.9% (12.5%)** |
| S5 Pidgin | 68.0% (45.8%) | 68.0% (47.2%) | 79.5% (33.3%) | **76.9% (29.2%)** |
| G English | 80.2% (25.3%) | 81.4% (18.0%) | 88.7% (24.0%) | **91.0% (26.7%)** |
| H | – (15.9%) | – (26.9%) | – (11.2%) | **– (9.3%)** |

- **Fine-tuning drives the gain.** Quantising to 4-bit costs little: F1 on S5 Yorùbá goes from 0.403 to 0.365; on G, from 0.718 to 0.685.
- **The 4-bit model is 3.3× smaller** (4.9 GB against about 16 GB) and runs on a laptop CPU with no internet.

**Checks after the fact** (reported, not used for verdicts):
- **G1 with item-level resampling:** −6.6 [−9.9, −3.5].
- **G1 with the worst case**, every schema-invalid output counted as a false alarm: −2.0 [−6.0, +1.98], still a pass.
- **Red team (R, 36 items):** too small to separate the systems. Recall was 81.3% for base and 75.0% for fine-tuned.

## 5. Real speech: S4-W (secondary, estimated with prediction-powered inference)
**Method:**
- committee labels on all 570 scored clips, plus a seeded human sample (120 labelled by the nurse Rahmat; 36 double-labelled, 25 of 25 overlapping labels agree);
- stratified PPI, with a cluster bootstrap over speakers (ADR-0025, `docs/results-s4w.md`).

| Input to the note model | Fine-tuned | Base | Difference [95% CI] |
|---|---|---|---|
| Human transcript | **13.2%** | 26.5% | **−13.3 [−15.9, −11.0]** |
| Fine-tuned speech recognition (as shipped) | **13.7%** | 24.3% | **−10.6 [−13.5, −7.6]** |
| Base N-ATLaS speech recognition | 15.2% | 25.1% | −9.9 [−13.5, −6.6] |

- **Safety audit:** humans found 0 danger signs that the committee missed (0 of 46 audited clips; upper 95% bound 6.3%).
- **Limits:**
  - recall is not estimable here, because the human sample holds no danger signs;
  - settling the 10 disputed clips the other way changes the difference to −12.9 [−15.3, −10.7].

## 6. Speech recognition fine-tuned on health speech (ADR-0026)
600 held-out test clips (35 speakers), paired bootstrap over speakers:

| Language | Base N-ATLaS ASR | Fine-tuned | Difference [95% CI] |
|---|---|---|---|
| Pidgin | 51.1% WER | **24.8%** | −26.3 [−32.4, −20.2] |
| Yorùbá | 44.7% WER | **38.0%** | −6.7 [−13.7, −2.7] |

General (non-health) speech improved too, on held-out training speakers: Pidgin from 47.9% to 16.3% WER; Yorùbá from 41.1% to 29.1%.

## 7. On a clinic laptop
**The reference hub:** Dell Latitude 5400 (i7-8665U, 4 cores, 16 GB, no GPU), with the shipped models and llama.cpp b11387.
- **The note model** (`results/hub/laptop-i7-8665u.json`; 8 non-test pilot notes):
  - a warm draft takes **124 s** at the median and 230 s at p95;
  - the first draft after start-up takes 408 s;
  - 8 of 8 outputs were valid, 5 of 6 danger signs were caught, with no false alarms.
- **The whole system:**
  - Tákàdá on a Galaxy S22 → laptop hotspot → hub;
  - speech recognition, the note model, the danger-sign rules, then review and confirmation on the phone;
  - first run on 10–11 Oct with test visits the team recorded.
- **What the system test found and fixed:**
  - a missed "baby moved well" denial, now flagged for checking (ADR-0030 cue);
  - records confirmed before the AI draft was asked for (the draft now starts by itself);
  - the hotspot switching itself off (an operations note);
  - an int8 decoding failure on long windows (below).

## 8. Smaller and faster: Tier 2 (ADR-0032, 11 Oct)
**Speech in int8 (CTranslate2).** Same models and same decoding; only the weights change. The rule was written before measuring: int8 may be at most 3 points worse in WER (upper bound of the CI). The numbers below are the re-check with the windows that ship (`results/asr/int8-dev-recheck.20261011.json`); int8 was 5.5–6.6× faster per clip.

| Model | Dev clips (public, not test) | fp32 WER | int8 WER | int8 − fp32 [95% CI] |
|---|---|---|---|---|
| Yorùbá fine-tune | FLEURS Yorùbá dev, 300 | 29.30% | 29.33% | +0.03 [−0.60, +0.67] |
| Pidgin fine-tune | AfriSpeech-200 dev (Nigerian accents), 300 | 30.57% | 30.23% | −0.35 [−1.05, +0.28] |
| English | AfriSpeech-200 dev, 300 | 16.78% | 16.97% | +0.20 [−0.48, +0.89] |

On the clinic laptop (`results/hub/int8-speech-laptop.20261011.json`):

| | fp32 | int8 |
|---|---|---|
| Memory, all three speech models loaded | 3.9 GB | **1.9 GB** |
| 20 s English recording | 55.7 s | **6.3 s** |
| 33 s Pidgin recording | 54.2 s | **22.6 s** |
| Disk per model | 967 MB | **242 MB** |

- **Found on the laptop and fixed:** int8 decoded one ~30 s window into 13 words where fp32 gave 78. Windows of at most 20 s match (78 = 78), so serving cuts recordings at pauses into windows of at most 20 s, and the dev check was re-run with them.
- **Confirmed on the test pool** (12 Oct, run once; 300 real clips per language; `results/asr/int8-test.20261012.json`):

  | Model | fp32 WER | int8 WER | int8 − fp32 [95% CI] |
  |---|---|---|---|
  | Yorùbá (16 speakers) | 28.90% | 29.26% | +0.36 [−0.09, +0.99] |
  | Pidgin (19 speakers) | 18.30% | 18.16% | −0.14 [−0.67, +0.30] |

  Both pass. **int8 now serves all three languages on the hub**, 6.5–7.2× faster per clip.
- **A 3-bit note model was rejected.** Q3_K_M and IQ3_M (4.0 and 3.8 GB, against 4.9 GB for Q4) both failed the pre-registered dev and pilot rule:
  - danger-sign recall on dev fell from 48.6% to 35.1% and to 40.5%;
  - details in `results/selection/lite-note-model.20261011.json`.

  8 GB laptops need a distilled model instead (ADR-0032 step 3).

## 9. Limits
- **Recall on real recorded speech is not yet measured:** real speech has too few danger signs, and recall comes from S5 and G.
- **About 1 in 3 Yorùbá and 1 in 4 Pidgin danger signs are missed (S5).** The nurse confirms every record, and the visit guide prompts the danger-sign questions.
- **No real-patient clinic use yet.** A pilot needs ethics approval and a data-protection impact assessment (ADR-0033).

## 10. Reproduce
- **Verdicts:**
  ```bash
  python scripts/final_scores.py --items <G+S5+H+R> --base results/frozen/base/frozen.pred.jsonl \
    --ft-q4 results/frozen/natlas-qlora-v1-weighted-fs-q4/frozen.pred.jsonl \
    --ft-hf results/frozen/natlas-qlora-v1-weighted-fs/frozen-b8.pred.jsonl \
    --base-q4 results/frozen/base-q4/frozen.pred.jsonl --out results/final/verdicts.json
  ```
- **S4-W:** `python scripts/ppi_score.py` (inputs hashed in `data/bench/s4w.ppi-inputs.json`).
- **Hub speed:** `python scripts/hub_check.py`.
- **Tier 2:** `deploy/modal_asr_int8.py` and `deploy/modal_gguf.py::lite_spawn`.
