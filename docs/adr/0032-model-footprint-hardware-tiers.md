# ADR-0032: Shrink the model footprint in three hardware tiers, after v1

- **Status:** Proposed (9 Oct 2026). Malik: "We will do all after we have a v1 to submit". **Nothing here changes v1.**
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
2. **Tier 2, note model:** a **lite variant** for 8 GB machines.
   - Candidates: IQ3_M / Q3_K_M of the same merged model, with the same training-text imatrix (about 3.6–3.9 GB; about 1 GB less RAM).
   - **Chosen on dev and pilot data only (ADR-0022).** It ships as an option next to Q4_K_M, never replacing it without a new pre-registered test.
3. **Tier 2→3, distillation:** the fine-tuned N-ATLaS is the teacher for a **1–3B student**, trained on teacher outputs over the training transcripts (never test items).
   - Goal: 1–2 GB, 3–5× faster, fits 8 GB laptops.
   - Needs its own ADR and a fresh pre-registered evaluation against the 8B on new frozen items.
   - Prefer a student from the N-ATLaS family if one exists by then, to keep the N-ATLaS lineage.
4. **Tier 3, phone only (roadmap):** the student at Q4 plus a tiny int8 ASR on the phone, so small clinics need no hub. Keep the hub for reporting and sync.

**Hardware tiers (for the submission's scalability section):**

| Tier | Hardware | Models | Status |
|---|---|---|---|
| 1 | 16 GB laptop hub | v1: 8B Q4_K_M + fp32 Whisper-Small | **measured (v1)** |
| 2 | 8 GB laptop hub | int8 ASR + lite or distilled note model | planned (this ADR) |
| 3 | phone, no hub | distilled student + tiny ASR | roadmap |

## Consequences
- **v1 is unchanged.** The tiers are presented as a plan, with only Tier 1 claimed as measured.
- **Each step brings its own evidence:** non-test data to choose, then a fresh pre-registered test. No frozen set is reused to pick a variant.
- **Operations now:** the hub guide must say "Docker Desktop: give WSL 12 GB (`%UserProfile%\.wslconfig`: `memory=12GB`)" until Tier 2 lands. This is a takada-app `docs/operations.md` change.
- **Install time:** int8 ASR and a lite model cut the first download roughly in half, which matters on clinic connections.
