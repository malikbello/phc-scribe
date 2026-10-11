# ADR-0032: Shrink the model footprint in three hardware tiers, after v1

- **Status:** Proposed (9 Oct 2026). Malik: "We will do all after we have a v1 to submit"; on 11 Oct, step 1 was brought forward ("needs to be done now"). **The v1 results are unchanged.**
- **Date:** 2026-10-09
- **Changes:** none until accepted. Later work changes the speech runtime, adds model variants, and needs new evaluations. The v1 artefact, its pre-registered frozen-test verdicts (P1, P2, G1, G2) and its ASR results (ADR-0026) are untouched.

## Context
A clinic hub today needs a **16 GB laptop**:

| Part | Disk | Notes |
|---|---|---|
| Note model: fine-tuned N-ATLaS 8B, imatrix Q4_K_M (ADR-0024) | 4.9 GB | about 5.5 GB RAM with the 8,192-token context |
| ASR fine-tunes, Yoruba and Pidgin (Whisper-Small, ADR-0026) | 1.9 GB | stored **fp32** (967 MB each) |
| English ASR (`NCAIR1/NigerianAccentedEnglish`) | about 1 GB | fp32 |
| API image | about 2 GB | already CPU-only torch |
| **Total** | **about 10 GB disk, 7–8 GB RAM** | Docker Desktop's default WSL limit (half of RAM, 8 GB on a 16 GB laptop) is too tight; the laptop dry run (9 Oct) raised it to 12 GB with `.wslconfig` |

Many primary health centres have 8 GB laptops, or none. Setup is also slow on clinic internet: at about 0.8 MB/s (laptop, 9 Oct), the first install downloads for 3–4 hours.

**Why not shrink v1 now:**
- every pre-registered result belongs to the 8B Q4_K_M;
- fine-tuned N-ATLaS is a judged criterion;
- choosing a smaller variant needs evaluation time we spend on S4-W and the submission.

## Decision (after the v1 submission, in this order)
1. **Tier 2, ASR (first: largest win, lowest risk):** convert the three Whisper-Small models to **int8 on CTranslate2** (faster-whisper).
   - Expected: about 0.75 GB in total instead of 2.9 GB, and 2–4× faster on CPU.
   - faster-whisper bundles Silero VAD (ONNX), so the ADR-0031 gate can drop its torch dependency.
   - **Accept only if** the WER on the ASR dev split (speaker-disjoint, ADR-0026) stays within the ADR-0026 test CIs' width of the fp32 models. Then re-test once on the ASR test pool, as a new pre-registered check.
   - Interim step, if needed: fp16 storage (half the disk; loaded as fp32 on CPU; no behaviour change).
   - **Brought forward and made precise, 11 Oct 2026, before any int8 measurement** (Malik: Tier 2 "needs to be done now"). The rule above was loose (CI widths of 11–12 points); this replaces it:
     - **Same decoding as serving:** greedy, language forced (yo → Yoruba; pcm and en → English), no timestamps, no conditioning on earlier windows, the H4 loop guard applied to both. Only the weights differ: fp32 (transformers) against int8 (CTranslate2).
     - **Dev check (chooses):** up to 300 clips per model of **public Nigerian speech that is not the test pool and that none of these models was fine-tuned on**:
       - the Yoruba model on **FLEURS Yoruba dev** (`google/fleurs`, `yo_ng`, CC-BY 4.0);
       - the Pidgin and English models on **AfriSpeech-200 dev**, Yoruba, Igbo and Hausa accents (`intronhealth/afrispeech-200`, CC BY-NC-SA 4.0, used for evaluation only). Nigerian-accented English, general and clinical. For the Pidgin model it is a fidelity check: the question is whether int8 changes the output, not how well the model knows English.
       - *Changed before any measurement:* the first plan (held-out WazobiaSpeech training speakers) failed on access. The gated dataset is not readable with the tokens available here (it was read on Kaggle before). No int8 number existed when the change was made.
     - **Rule (non-inferiority, per model):** the 95% paired bootstrap interval of int8 WER minus fp32 WER has an **upper bound ≤ +3.0 points**, resampling speakers (AfriSpeech) or sentences (FLEURS, which has no speaker ids; each sentence is read by a few people).
     - **Test-pool check (confirms, run once):** the same rule on the 600 test-pool clips (ADR-0026), for Yoruba and Pidgin. int8 becomes the hub default only if both checks pass for a model; otherwise that model stays fp32, and the result is reported either way.
     - **Also measured, not part of the rule:** load memory and seconds per clip on the same CPU, and later on the pilot laptop.
2. **Tier 2, note model:** a **lite variant** for 8 GB machines.
   - Candidates: IQ3_M / Q3_K_M of the same merged model, with the same training-text imatrix (about 3.6–3.9 GB; about 1 GB less RAM).
   - **Chosen on dev and pilot data only (ADR-0022).** It ships as an option next to Q4_K_M, never replacing it without a new pre-registered test.
   - **Rule, written 11 Oct 2026 before any 3-bit result:**
     - candidates Q3_K_M and IQ3_M, built from the same merged model with the same training-text imatrix (`deploy/modal_gguf.py::lite_spawn`);
     - each is scored with the shipped Q4_K_M, same llama.cpp and prompt, on dev (127 items) and pilot (30);
     - a candidate qualifies only if **on both sets**: danger recall at most 5 points below Q4, micro-F1 at most 0.03 below, false alarms at most 5 points above, and schema-valid at least 95%;
     - of those that qualify, the smaller file is offered as the 8 GB option;
     - none qualifying is a result too, and is reported. Dev is small (41 groups), so this is a screen, not proof.
3. **Tier 2→3, distillation:** the fine-tuned N-ATLaS is the teacher for a **1–3B student**, trained on teacher outputs over the training transcripts (never test items).
   - Goal: 1–2 GB, 3–5× faster, fits 8 GB laptops.
   - Needs its own ADR and a fresh pre-registered evaluation against the 8B on new frozen items.
   - Prefer a student from the N-ATLaS family if one exists by then, to keep the N-ATLaS lineage.
4. **Tier 3, phone only (roadmap):** the student at Q4 plus a tiny int8 ASR on the phone, so small clinics need no hub. Keep the hub for reporting and sync.

**Hardware tiers (for the submission's scalability section):**

| Tier | Hardware | Models | Status |
|---|---|---|---|
| 1 | 16 GB laptop hub | v1: 8B Q4_K_M + fp32 Whisper-Small | **measured (v1)** |
| 2 | 8 GB laptop hub | int8 ASR + lite or distilled note model | **int8 speech: built and dev-checked (11 Oct)**; note model planned |
| 3 | phone, no hub | distilled student + tiny ASR | roadmap |

## Result: step 1, int8 speech (11 Oct 2026, dev check)
`deploy/modal_asr_int8.py`; numbers in `results/asr/int8-dev.20261011.json`. 300 clips per model, one at a time on 8 vCPU, the decoding above.

| Model | Dev clips | fp32 WER | int8 WER | int8 − fp32 [95% CI] | Rule (upper ≤ +3.0) | Seconds per clip, fp32 → int8 |
|---|---|---|---|---|---|---|
| Yoruba fine-tune | FLEURS Yoruba dev (137 sentences) | 29.57% | 29.52% | −0.04 [−0.62, +0.52] | **pass** | 5.75 → 1.23 (4.7×) |
| Pidgin fine-tune | AfriSpeech dev, 3 Nigerian accents (84 speakers) | 30.25% | 29.94% | −0.30 [−1.04, +0.38] | **pass** | 3.10 → 1.36 (2.3×) |
| English (NCAIR1) | the same AfriSpeech clips | 16.73% | 16.69% | −0.04 [−0.77, +0.76] | **pass** | 2.88 → 1.36 (2.1×) |

- **Size on disk:** 967 MB → 253 MB per model (−74%).
- **Memory** is measured on the pilot laptop (results/hub/), not here: transformers maps fp32 weights lazily, so an in-process difference is not a fair figure.
- **Still to run before int8 becomes the hub default for Yoruba and Pidgin:** the test-pool check (ADR-0026's 600 WazobiaSpeech clips, same rule). It needs the gated dataset, which the tokens available on 11 Oct could not read. Until it passes, the hub ships int8 as an option (`PHC_ASR=ct2`) and keeps fp32 as the default. English had no test-pool check planned, so its dev check is its gate.

**Found on the pilot laptop the same day, fixed, and re-checked:**
- **The bug:** a 33 s Pidgin recording, decoded in one ~30 s window, gave 13 words with int8 and 78 with fp32. With windows of at most 20 s the two matched (78 = 78; at 15 s, 80 = 80).
- **The fix:** serving now cuts any recording over 20 s at pauses into windows of at most 20 s (`INT8_WINDOW_S`).
- **The dev check was re-run** with exactly these windows for both versions, since the decoding that ships had changed. Results:
  - Pidgin: 30.57% → 30.23%, −0.35 [−1.05, +0.28], **pass**, 5.5× faster;
  - English: 16.78% → 16.97%, +0.20 [−0.48, +0.89], **pass**, 5.9× faster.
- **Laptop** (`results/hub/int8-speech-laptop.20261011.json`): with all three speech models loaded, peak memory falls from 3,908 MB to **1,871 MB**. A 20 s English recording takes 6.3 s instead of 55.7 s.
- **On the hub since 11 Oct:** English uses int8 (`PHC_ASR_INT8_MODELS=en=…`); Yoruba and Pidgin stay on fp32.

## Result: step 2, a 3-bit note model (11 Oct 2026): rejected
`deploy/modal_gguf.py::lite_spawn`; `results/selection/lite-note-model.20261011.json`. Same merged model, same training-text imatrix, same llama.cpp and prompt; dev 127 items, pilot 30; no frozen item.

| Model | Size | Dev recall | Dev F1 | Dev false alarms | Pilot recall | Pilot F1 | Rule |
|---|---|---|---|---|---|---|---|
| Q4_K_M (ships) | 4.92 GB | 48.6% | 0.437 | 7.5% | 90% | 0.738 | n/a |
| Q3_K_M | 4.02 GB | 35.1% | 0.389 | 7.5% | 80% | 0.730 | **fails:** dev recall, dev F1, pilot recall |
| IQ3_M | 3.78 GB | 40.5% | 0.337 | 10.7% | 85% | 0.667 | **fails:** dev recall, dev F1, pilot F1 |

- **Neither qualifies.** Saving about 1 GB costs too many danger signs, so no 3-bit option ships.
- **8 GB laptops wait for step 3** (a distilled 1–3B student). The 3-bit files stay on the runs volume only.

## Consequences
- **v1 is unchanged.** The tiers are presented as a plan, with only Tier 1 claimed as measured.
- **Each step brings its own evidence:** non-test data to choose, then a fresh pre-registered test. No frozen set is reused to pick a variant.
- **Operations now:** the hub guide must say "Docker Desktop: give WSL 12 GB (`%UserProfile%\.wslconfig`: `memory=12GB`)" until Tier 2 lands. This is a takada-app `docs/operations.md` change.
- **Install time:** int8 ASR and a lite model cut the first download roughly in half, which matters on clinic connections.
