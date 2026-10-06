# Pre-freeze audit, 4 Oct 2026

Requested by Malik before the stage-1 freeze: "go back and do the audit and make sure nothing is amiss". Every pre-registered item in `docs/eval-plan.md` was checked against the data and the code, every test and training set against every other for leakage, and open datasets were re-surveyed.

**Verdict: freezing as planned would have locked in a test set that cannot answer the primary question.** Three critical fixes are needed before the freeze. Most other findings are quick fixes, done below or scheduled.

## Critical

### C1. The counted test set has too few danger signs to test P1
- **Evidence:**
  - A keyword pass over the 600 S4-W clips finds about **15 with a danger sign** (13 fever, 2 vaginal bleeding; 14 of them Yoruba).
  - Over the whole Yoruba `dev` + `dev_test` health pool it finds **55 of 5,584 clips (1%)**.
  - The committee's 16-item smoke run found no findings at all.
  - The clips are health-education talk, where the guidelines say "nothing to record" unless the speaker is the patient.
- **Rule broken:** eval plan §3, "at least 30% of test items contain at least one danger sign". S4-W has about 2.5%.
- **Consequence:** with about 15 positives, the 95% CI on a recall difference is wider than ±25 points. P1 would fail for lack of data, not of model quality.
- **Fix (proposed; needs Malik's decision):**
  - **Primary danger-sign test for Yoruba and Pidgin:** a prospective, OSCE-style role-play stratum (C2 below).
  - **English:** on G (300 generated notes, 226 with a danger sign) and the MamaBench ANC slice (78 clinician-authored, 37 with a danger sign).
  - **S4-W stays counted** for what it measures well: false alarms on real speech (G1), micro-F1, and recall as a secondary.

### C2. P1 and the research question name the wrong languages
- **Evidence:**
  - §1 asks about "Yoruba and English".
  - P1 requires a gain "in English and in Yoruba".
  - The counted real-speech set is Yoruba and **Pidgin**, with no English.
- **Cause:** the wording dates from 29 Sept, when the counted set was planned as English AMR notes plus Yoruba. ADR-0016 and ADR-0018 changed the data on 30 Sept, and §1 and §6 were not updated. **This should have been caught when those ADRs were accepted.**
- **Fix:** amend §1 and §6 before the freeze (dated section, as §6 already requires).

### C3. The comparison runtime is unspecified, and the shipped-model (Q4) runner does not exist
- **Evidence:**
  - P1 compares "fine-tuned Q4 − base few-shot". The base runs use Hugging Face transformers in fp16 with xgrammar.
  - The Q4 GGUF runs in llama.cpp. There is no llama.cpp evaluation runner in `bench/`; only the serving `LlamaCppExtractor` exists.
  - The two runtimes apply the repetition penalty differently: HF over every previous token, llama.cpp over the last 64 tokens by default.
- **Fix:**
  - Build a llama.cpp runner with the same prompt, schema and grammar, and `repeat_last_n = -1`, so the penalty covers the whole context as HF does.
  - Score a 2×2 (base / fine-tuned × HF fp16 / llama.cpp Q4), so the fine-tuning effect and the quantisation effect are reported separately.
  - P1 stays fine-tuned Q4 against base few-shot, as pre-registered. The 2×2 shows the comparison is not a runtime artefact.

## High

| # | Finding | Evidence | Fix |
|---|---|---|---|
| H1 | §4 gold-label procedure contradicts ADR-0025 | §4 says all-human labels with a 60-item κ overlap; ADR-0025 uses the committee, a random human sample and PPI | Rewrite §4 to ADR-0025 (κ from the double-labelled sample) |
| H2 | The "audio through N-ATLaS ASR" test condition has no builder | Base and fine-tuned ASR test transcripts exist (`asr-*-forced.jsonl`), but no code makes test items from them | Build S4-W-ASR items (ASR text in, human gold) and score them |
| H3 | Repeated sentences across WazobiaSpeech splits | 22 teacher training clips have a test clip's exact sentence (different speakers) | **LLM:** `build_train_set.py` drops exact and near duplicates of test text; check that the build reports them. **ASR:** re-scored on test sentences never in ASR training (below); the gain holds |
| H4 | The fine-tuned Pidgin ASR looped on one clip | 222 words for a 23-word reference: 220 of its 2,404 Pidgin errors | Add a decoding guard (repetition / compression-ratio check) in `serve/phc_scribe/api/asr.py`; re-score as shipped |
| H5 | Pre-registered strata not built | Red-team R (~60), the MamaBench ANC slice (78) and AMR (62) have no bench files | Build MamaBench (English, clinician-authored) and a small R set; drop AMR |
| H6 | The eval plan still calls ADR-0018 "proposed" (it was accepted 1 Oct) | MAMAI still awaits Intron's review on 4 Oct; the files list but downloads return 403 | Corrected in §3; S4-W is in use (Malik, 4 Oct: "we can't keep waiting") |

**ASR re-scored on test sentences never seen in ASR training** (`scripts/asr_compare.py` logic, 4 Oct):

| Language | Clips | Base WER | Fine-tuned WER | Difference [95% CI] |
|---|---|---|---|---|
| Pidgin | 283 | 51.0% | 22.7% | −28.2 [−32.7, −23.2] |
| Yoruba | 273 | 45.4% | 38.8% | −6.5 [−13.9, −2.4] |

The ASR gain is acoustic, not memorised text. The never-seen-sentence numbers are the ones to headline.

## Medium

| # | Finding | Fix |
|---|---|---|
| M1 | §7 says every run is logged in MLflow; none is (results JSON plus git instead) | Correct §7 |
| M2 | §5 promises Yoruba metrics with and without tone-mark folding; the harness has no folded report | Add to the harness, or drop from §5 |
| M3 | Laptop CPU latency (i7-8665U) not yet measured | After the GGUF build |
| M4 | Error-analysis taxonomy pending | After scoring |
| M5 | The S4-W row says `dev_test`; the pool is `dev` + `dev_test` | Correct §3 |
| M6 | HF token is read-only, so publishing is blocked (correct least privilege) | Malik creates a separate write token |
| M7 | Llama-3.1-8B is both the training-label teacher and baseline rung 2 | Disclose; it is a fair comparator, and the committee excludes it (ADR-0025) |

## Checked and clean
- **Few-shot examples** (from `tests/fixtures/smoke_items.jsonl`): in no test or training set.
- **Pilot, G, H:** no shared text, groups or ids with each other or with any training data.
- **Speakers:** test speakers are disjoint from every training speaker (0 shared speaker groups between the teacher clips and S4-W).
- **ASR fine-tune:** used only `train` shards, never `dev`/`dev_test`; the 460 LLM two-view clips were excluded.
- **Base comparator decoding rule:** run and recorded (repetition penalty 1.12).

## Open datasets re-surveyed (4 Oct)

| Dataset | What it is | Use for us |
|---|---|---|
| NigBench-MAMAI-Speech-QA (Intron) | Maternal-health speech QA, 7 Nigerian languages (Yoruba ≈ 52 h), CC-BY-4.0 | **Still gated (manual review pending).** Swap in if access arrives before the freeze |
| AfriSpeech-Dialog (Intron) | 50 simulated (OSCE-style) medical and non-medical conversations, African-accented English; clinicians as actors; CC-BY-NC-SA-4.0, open | English real-speech conversation check; also shows the field builds clinical-speech tests by role-play |
| ACI-Bench (Microsoft/Nuance), PriMock57 | Role-played doctor–patient consultations with notes | Precedent: clinical-scribe benchmarks are built from role-play |
| Google WAXAL | ~1,250 h transcribed speech, 21 African languages incl. Yoruba, Hausa, Igbo; CC-BY-4.0 / CC-BY-SA-4.0 | More Yoruba ASR training data (Yoruba ASR is the weaker of the two) |
| NaijaVoices, NaijaS2ST | Large Yoruba/Igbo/Hausa speech corpora | ASR training candidates |
| Antenatal orientation speech (Ajagbe 2024) | Real antenatal teaching, en/yo/pcm | Already used (stratum H, false alarms) |

**No open dataset of real antenatal consultations in Yoruba or Pidgin exists** apart from gated MAMAI. Role-play consultations are how the field solves this: AMIE's patient actors, ACI-Bench, PriMock57, and Intron's own AfriSpeech-Dialog.

## Fix status (4 Oct, same day)

| # | Status |
|---|---|
| C1 | **Fixed.** S5 built (`bench/constructed.py`, `data/bench/s5.20261004.jsonl`): 300 constructed Yoruba and Pidgin patient statements, 78 danger-sign items per language, all 12 patient-reportable danger signs, gold by construction. Eval plan §6a makes S5 (yo, pcm) and G (en) the P1 sets. Malik ruled out recording role-play visits (no time). |
| C2 | **Fixed.** §6a: Yoruba, Pidgin and English, with the test set for each. |
| C3 | **Specified** in §6a (runtimes, `repeat_last_n = -1`, the 2×2 table). The llama.cpp runner is built once the adapter exists (the GGUF needs it). |
| H1 | **Fixed.** §6a replaces §4 with ADR-0025. |
| H2 | **Fixed.** `scripts/build_asr_items.py` (+ test): S4-W gold with ASR text as input. |
| H3 | **Fixed for the LLM** by the builder's duplicate filter (counts to be checked at build). **ASR re-scored** on never-seen sentences (table above). |
| H4 | **Guard built 6 Oct** (`serve/phc_scribe/asr_guard.py`, in `/v1/transcribe`): Whisper's compression-ratio check (> 2.4); repeated word n-gram runs cut to 2 copies; ordinary text untouched. **Re-scored 6 Oct, both systems guarded** (`results/asr/ft-vs-base.guarded.20261007.json`): Pidgin 51.1% → **22.7%** (−28.3 [−32.8, −23.4]); Yoruba 41.1% → **31.6%** (−9.6 [−12.7, −5.1]). The guard helps both models (base Yoruba loops too); the fine-tuned gain holds. **Closed.** |
| H5 | **Decided** in §6a: MamaBench and AMR dropped; R built as a small constructed set (pending). |
| M1, M5, H6 | **Fixed.** |
| M2 | **Decided** in §6a: the folded-match count is reported per system. |
| M3, M4 | After scoring. |
| M6 | Waiting for Malik's write token. |
| M7 | Disclosed in §6a and in the model card. |
