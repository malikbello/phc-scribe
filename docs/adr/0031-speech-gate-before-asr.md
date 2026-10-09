# ADR-0031: A voice-activity gate before Whisper: no speech, no transcript

- **Status:** Accepted by Malik, 10 Oct 2026 ("Yes on the PRs"). Proposed 8 Oct 2026; built and tested.
- **Date:** 2026-10-08
- **Changes:** `/v1/transcribe` with `PHC_ASR=hf`:
  - Silero VAD runs first on clips of 2 s or more; under 0.25 s of speech, Whisper is not run and `text` is empty;
  - new `speech_s` field;
  - `PHC_ASR_VAD=on|off` (default on);
  - new pinned dependency `silero-vad==6.2.3` in `deploy/api.Dockerfile` and `deploy/modal_app.py`.

  The ASR evaluation (ADR-0026) and its test results are unchanged: clips with speech go to Whisper exactly as before.

## Context
Whisper-family models write fluent text for silence and noise. In the 7 Oct hub run (takada-app `docs/reviews/2026-10-07-pilot-readiness.md`, B7 and O2), a silent recording became "are there cultural rituals that help orphaned individuals commemorate their heritage?". Takada now refuses digital silence (B7), but real noise (a phone in a pocket, a fan, a crowd) still reaches Whisper.

**Options considered:**
- **Whisper's own no-speech probability:** not exposed by the chunked pipeline, and fine-tuning (ours, ADR-0026) degrades its calibration, so it is unreliable here.
- **Energy thresholds:** pass any loud noise.
- **A trained VAD before Whisper:** the standard remedy (faster-whisper's `vad_filter`, WhisperX), both with **Silero VAD**. It is MIT-licensed, about 2 MB, ships inside the `silero-vad` wheel (works offline on the hub) and depends only on torch, which the image already has.

## Decision
1. **Gate, don't trim.** The VAD only decides whether a clip has speech. A clip with speech goes to Whisper whole and unchanged, so no transcript of a real recording changes. Trimming pauses could also cut hallucination inside long pauses, but it changes transcripts, so it would need its own dev-data evaluation and ADR.
2. **Thresholds, fixed before the check:**
   - Silero's default (0.5);
   - under **0.25 s** of detected speech, the clip has none;
   - clips under **2 s** are always transcribed, because a lone word is too short for the VAD to be sure of (see Evidence).
3. **Visible:** `speech_s` is returned, and an empty transcript is not text. Takada counts such a recording as "no speech heard", tells the health worker, and never drafts from it.

## Evidence
Non-test audio only. `scripts/vad_check.py` refuses frozen folders; results are in `results/asr/vad-gate.fleurs-dev.20261008.json`.
- **Speech** (61 clips: 40 Yoruba and 20 English clips from Google FLEURS `dev`, CC-BY 4.0, used by no benchmark here, plus one synthetic English visit):

  | Variant | Passed |
  |---|---|
  | Clean | 61 of 61 |
  | White noise at 5 dB SNR | 61 of 61 |
  | White noise at 0 dB SNR | 59 of 61 |
  | Cut to 0.5 s (always transcribed under the 2 s rule) | 61 of 61 |

  By the VAD alone, a 0.5 s word passed only 38 of 61 (48 of 60 with quiet around it). That is why short clips are never gated.
- **Non-speech** (48 sounds: silence, hiss, white/pink/brown noise, mains hum, a fan, taps and tones, at -35 and -20 dBFS, 3 seeds): **0 of 48 passed**.
- **A sweep of the VAD threshold (0.25–0.5), tuned on half the clips and checked on the other half:** no gain on short words, and 0 noise passed at every setting, so the default stays.

## Limits
- **No WazobiaSpeech train audio:** this account is not on that gated dataset's access list, so FLEURS was used: read speech, Yoruba and English, no Pidgin.
- **Babble is untested:** other people talking is speech, and the gate passes it by design. Telling the patient from the room is not a VAD's job.
- **No real-device recordings yet:** the 9 Oct pilot recordings are the first real check.
