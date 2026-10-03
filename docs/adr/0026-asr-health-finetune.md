# ADR-0026: Fine-tune N-ATLaS ASR on Yoruba and Pidgin speech (health-domain evaluation)

- **Status:** Proposed, 3 Oct 2026. Needs Malik's approval.
- **Date:** 2026-10-03
- **Changes:** adds a second fine-tuned N-ATLaS component. Architecture §6 fine-tuned the LLM only; ASR used the NCAIR1 models as released.

## Context
- **Speech recognition is the first step** of the shipped pipeline (audio → N-ATLaS ASR → fine-tuned N-ATLaS → record). Every word it gets wrong is lost before the LLM sees it.
- **First signal (3 Oct, 2 test-pool Pidgin clips): 43% and 56% word error rate.** N-ATLaS has no Pidgin ASR, so Pidgin goes through `NCAIR1/NigerianAccentedEnglish`. Run A measures WER on all 600 test-pool clips, per language; that is this ADR's baseline.
- **Fine-tuning Whisper on the target speech is the best-evidenced fix.** NaijaVoices reports a **75.9% average WER improvement for Whisper** after 5 epochs on Nigerian-language speech ([arXiv 2505.20564](https://arxiv.org/abs/2505.20564)). Intron's lead over global models comes from African speech data, not model size ([AfriSwitch](https://arxiv.org/abs/2608.26434)).
- **Judging:** criterion 2 rewards depth of N-ATLaS integration, "model, API, ASR service or **training pipeline**". Fine-tuning the N-ATLaS ASR models as well as the LLM is the deepest integration available, and a Pidgin-capable N-ATLaS ASR is new.
- **Data:** WazobiaSpeech `train` (CC-BY-4.0, pinned revisions, ADR-0018) has hundreds of hours per language. Its speakers are disjoint from the `dev` + `dev_test` test pool (checked over all shards, 1 Oct).

## Decision
1. **Models:** fine-tune `NCAIR1/Yoruba-ASR` on Yoruba, and `NCAIR1/NigerianAccentedEnglish` on Pidgin (decoded as English, the closest Whisper language). Both are Whisper-Small (244M), full fine-tuning in fp16 on a Kaggle T4.
2. **Data:** all clips (every domain, for acoustic coverage) from 30 evenly spaced `train` shards per language, about 12,000 clips and 30+ hours each, plus every `train` health clip in those shards. Never `dev` or `dev_test`.
3. **Recipe:**
   - learning rate 1e-5 with warmup;
   - 2 epochs;
   - batch 16 (gradient accumulation);
   - SpecAugment;
   - the language forced in training and decoding;
   - long clips split into ≤30 s windows aligned to the transcript.
   - Choices are made on a held-out slice of `train` speakers, never the test pool.
4. **Evaluation:**
   - WER and CER on the 600 test-pool clips, against the base NCAIR1 models (Run A), with paired bootstrap CIs per language;
   - also the end-to-end benchmark with ASR input (eval plan, S4 audio condition).
5. **Ship rule:** the fine-tuned ASR replaces the base model in the hub and API only if its test WER is better with the CI excluding zero. Otherwise the base model stays, and the result is reported.
6. **Naming and licence:** published gated, as "N-ATLaS ASR Health (yo, pcm) · Powered by Awarri", under the N-ATLaS Terms.

## Consequences
- **Upside:**
  - fixes the measured weakest link;
  - deepens integration (criterion 2);
  - gives a second headline result: a WER reduction on real Nigerian health speech.
- **Cost:** about 4–5 GPU hours (data loading dominates), within the weekly free quota alongside the LLM runs.
- **Risks:**
  - Time: it runs in parallel with the LLM pipeline, and nothing depends on it except the audio condition.
  - Forgetting general speech: reported on a non-health held-out slice.
  - Pidgin spelling varies: WER is reported on folded text, as everywhere else.
