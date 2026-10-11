# ADR-0033: Keep recordings and transcripts only as long as the record needs them

- **Status:** Proposed (11 Oct 2026). Malik asked what a mature team does about pilot-review finding O4 ("audio and transcripts are kept forever").
- **Date:** 2026-10-11
- **Changes:** takada-app hub server (a purge job, two settings) and phone app (local clean-up, a consent tick). phc-scribe's `/v1/extract` and `/v1/transcribe` already keep nothing (only `/v1/records` stores, and the hub does not use it). The model, benchmark and results are unchanged.

## Context
A visit produces three kinds of personal data, all **health data**, which Nigeria's Data Protection Act 2023 (NDPA) treats as sensitive:

| Data | Where it lives today | How identifying |
|---|---|---|
| **Recording** (the woman's and the nurse's voices) | phone (IndexedDB) until uploaded; hub `AUDIO_DIR/<visit>/` **forever** | Most: a voice identifies a person |
| **Full transcript** (everything said) | hub event log (`draft.received`) and phones that pulled it, **forever** | High: names, places, other people's details said in passing |
| **Confirmed record** (findings, measurements, short evidence quotes) | phone and hub event log | Lower: the patient is an ANC card number or initials ("Never her full name", Takada's visit form) |

The confirmed record is the clinical record, so it belongs to the facility and is kept under its medical-records policy, not ours. The recording and the full transcript are **working material**: the record needs them only until the nurse has confirmed it and has had time to correct it. The NDPA's principles (purpose limitation, data minimisation, storage limitation, security, accountability) say working material should not outlive its purpose.

## Decision
1. **Ask before recording.** The visit form gets a "She agrees to the recording" tick. Without it the record button is off, and typed notes still work. The tick is stored with the visit.
2. **The phone deletes its copy of a recording** once the hub has stored it **and** the record is confirmed. Until both are true, the phone is the only copy, so it keeps it.
3. **The hub deletes recordings and full transcripts:**
   - **7 days after a record is confirmed** (`RETAIN_AUDIO_DAYS`, default 7). This is the window for "Correct this record" and a fresh draft from the same recording;
   - **30 days after an unconfirmed visit started** (`RETAIN_UNCONFIRMED_DAYS`, default 30), for visits nobody finished;
   - an amendment reopens a record, so its clock restarts at the next confirmation.
4. **How a transcript is removed from an append-only log:** the hub re-issues its own `draft.received` event for that visit with an empty transcript and a new content hash. Only server-authored events are rewritten, never a worker's event. Findings and their evidence quotes stay, so the confirmed record and its `recordHash` are unchanged.
5. **Accountability:** every purge is logged in a `purges` table (visit, time, files deleted, transcripts removed): counts only, never content. The hub log reports the counts.
6. **Never off the hub by default.** Recordings and transcripts go to no cloud service. Using them to improve the models would need separate, explicit consent and a new ADR.
7. **Security that already holds:** TLS from the phone to the hub (the hub's own CA), a device token per phone, pseudonymous patient references, and nothing stored by the speech and note API. Before a real pilot: BitLocker on the hub laptop, the phone's own encryption (on by default on current Android), and a DPIA with the facility.

## Consequences
- **A smaller breach:** a lost hub laptop holds at most a week of recordings, not every visit ever.
- **Cost:** "Draft again" works for 7 days after confirmation. After that, a correction is typed. Unfinished visits lose their recording after 30 days.
- **Phones that already pulled a transcript** keep it until their own clean-up runs. The phone clears transcripts of confirmed visits on the same 7-day clock (step 2's follow-up, after v1).
- **Not decided here:** the facility's retention period for confirmed records, the right to erasure for a confirmed record (an admin endpoint), and registration with the NDPC if Takada becomes a data controller of major importance. These come with the first real-clinic pilot, with the facility and its ethics approval.
