# ADR-0034: Live listening during the visit (v2)

- **Status:** Proposed (11 Oct 2026), for after v1. Malik described the product he expects: "the AI listens, flags questions not yet asked, raises a silent alarm when it hears a danger sign, then helps fill the form, and the nurse reviews, confirms and signs off".
- **Date:** 2026-10-11
- **Changes:** none in v1. Later work changes takada-app (chunked upload, partial transcripts, live hints) and the hub's speech queue. The note model, the benchmark and its results are unchanged.

## Context
**v1 is a two-speed design:**
- *During the visit,* the phone runs fixed, offline rules:
  - one question at a time from the WHO-based visit guide;
  - an instant on-screen alarm when the nurse taps a danger sign.
- *After the visit,* the hub drafts the record from the recording: speech to text, then the fine-tuned N-ATLaS. The nurse reviews and holds to confirm (sign-off).

**The AI does not hear the visit while it happens.** On the pilot laptop, fp32 speech recognition ran slower than the speech itself (55.7 s for a 20 s clip), and the 8B note model writes about 1.5 words a second.

**Tier 2 speech changed the first half** (ADR-0032, measured 11 Oct): int8 transcribes a 20 s clip in about 6 s on the same laptop, about 0.3× real time. Speech can now keep up with a visit; the note model still cannot.

## Decision (after v1)
1. **Chunks while recording.** The phone already saves the recording every second (O3). On the clinic Wi-Fi it also sends each 20 s of speech to the hub as it is recorded.
2. **Partial transcripts.** The hub transcribes each chunk with int8 speech, ahead of whole-visit drafts in the queue. It returns a `transcript.partial` event within about 10–30 s of the words being said.
3. **Live hints on the phone, from the same deterministic engines as today; no LLM in this loop:**
   - **Questions:** the visit guide marks a question covered when the partial transcript covers it (`guideOf` already reads transcript text). "Ask next" then moves on, so the nurse is prompted only for what has not been asked.
   - **Silent alarm:** danger-sign words heard in the partial transcript (the vocabulary's English, Yoruba and Pidgin forms; phc-scribe's keyword extractor) raise a quiet banner: "Heard: bleeding. Check and confirm." A hint is never written into the record. It becomes a finding only through the nurse's tap or the final draft.
4. **The record is still drafted once, at the end,** by the fine-tuned N-ATLaS, and is reviewed and confirmed as now.
5. **Evidence before it ships,** pre-registered, on recorded non-test visits:
   - the delay from words to hint;
   - live hints against the final confirmed record (precision and recall per danger sign);
   - false hints per visit (alarm fatigue);
   - a threshold for each, written before measuring.

## Consequences
- **What it needs:** Tier 2 speech for every language. English is live; Yoruba and Pidgin are waiting for their test-pool check (ADR-0032).
- **Design rule kept:** rules decide danger signs, and the model documents. Live hints are a prompt to look, never a diagnosis.
- **Costs:**
  - more hub work per visit (each chunk is transcribed once and reused for the final draft, so the total speech work does not grow);
  - more Wi-Fi traffic during the visit.
- **Privacy:** chunks are recordings and follow ADR-0033 retention.
- **The pitch can say** "live listening is next, and the speed it needs is already measured". It cannot say it ships.
