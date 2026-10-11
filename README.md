# PHC Scribe

**An offline AI scribe and safety net for antenatal care in Nigeria's primary health centres, built on N-ATLaS.**

A nurse talks with a pregnant woman in Yorùbá, Nigerian Pidgin or English while **Tákàdá**, the phone app, records the visit. A laptop in the clinic, working with no internet, turns the conversation into a structured antenatal record with the fine-tuned N-ATLaS:
- findings, with the words they came from;
- measurements;
- the danger signs, flagged by fixed rules based on WHO antenatal guidance.

The nurse checks the draft, corrects it if needed, and holds to confirm. The record, a referral note and a FHIR R4 export follow from that.

> Entry for the **National AI Innovation Challenge 2026** (NCAIR / ONDI / FMCIDE), **Problem Statement 3, Sectoral Fine-Tuning: primary health care**.

## Why
- Nigeria has **28.7% of the world's maternal deaths** (about 75,000 in 2023) and about **one doctor per 9,000 people**. Most antenatal care is given by nurses, midwives and community health workers.
- Writing records takes about **a third of consultation time**.
- The conversation is in Yorùbá, Pidgin, Hausa or Igbo, but the record must be in English.
- Clinics lack reliable power and internet, so cloud-only tools cannot serve them.

## Results at a glance
Every main result was **pre-registered** before it was measured (`docs/eval-plan.md`). It was scored once on frozen test sets that no choice was tuned on (ADR-0022), with 95% bootstrap intervals. The comparison is always against **base N-ATLaS**.

| What | Base N-ATLaS | PHC Scribe (shipped, 4-bit on a laptop CPU) | Difference [95% CI] |
|---|---|---|---|
| Danger signs found: Yorùbá patient statements (S5, constructed; 78 danger items) | 52.6% | **67.9%** | +15.4 [+4.8, +26.4] |
| Danger signs found: Pidgin patient statements (S5, constructed; 78) | 68.0% | **76.9%** | +9.0 [+1.3, +17.2] |
| Danger signs found: English antenatal notes (G, generated; 226) | 80.2% | **91.0%** | +10.7 [+4.0, +17.6] |
| False alarms: real antenatal teaching sentences, en/yo/pcm (H, 454) | 15.9% | **9.3%** | −6.6 [−10.8, −2.7] |
| **False alarms: 570 real Yorùbá and Pidgin health speech clips (S4-W)** | 26.5% | **13.2%** | **−13.3 [−15.9, −11.0]** |
| General Yorùbá ability kept (Belebele, 900) | 42.9% | 42.2% | −0.7 [−2.1, +0.8] |

The sets are labelled as they are:
- **S4-W and H are real** speech and text;
- **S5 and G were written for the benchmark**, so that every danger sign occurs often enough to measure. Real speech has about 2.5% danger signs, too few to test recall.

- **All four pre-registered tests pass** (`docs/results-frozen-tests.md`). S4-W is estimated with a human audit and a safety stop (ADR-0025, `docs/results-s4w.md`).
- **Speech recognition fine-tuned on Nigerian health speech** (ADR-0026), measured on 600 held-out test clips:
  - Pidgin word errors fell from 51.1% to **24.8%**;
  - Yorùbá word errors fell from 44.7% to **38.0%**.
- **Runs on a clinic laptop** (i7-8665U, 16 GB, no GPU):
  - the note model drafts a record in about 2 minutes (median of 8 pilot notes);
  - with the int8 speech models (ADR-0032), a 20 s recording is transcribed in about 6 s instead of 56 s, using half the memory.

## How it works
```
 Phone: Tákàdá (offline web app; Android and iPhone builds)
   record the visit (consent asked first) · one question at a time from the visit guide
   instant danger-sign alarm on a tap · works with no network, syncs on the clinic Wi-Fi
        │  HTTPS on the clinic Wi-Fi (the hub's own certificate)
        ▼
 Clinic hub: a laptop running Docker, no internet needed
   Tákàdá server: sync, drafting queue, FHIR R4 export, retention of recordings (ADR-0033)
   PHC Scribe API (/v1): voice-activity gate → N-ATLaS speech recognition (fine-tuned
     Yorùbá and Pidgin; int8 option) → fine-tuned N-ATLaS 8B (4-bit, llama.cpp)
     → schema check, grounding, polarity check → danger-sign rules
```
- **Rules decide danger signs; the model only documents.** Each rule names its WHO source (`rules/danger_signs.v0.yaml`).
- **The nurse confirms every record:**
  - model findings are marked "AI draft", with the words they were heard in;
  - a finding whose quote reads as a denial or a normal state gets a "Please check" note (ADR-0030).
- **Speech the model should not trust is stopped early:** silence and noise never reach Whisper (ADR-0031), and decoding loops are cut (audit H4).
- **The same API also runs as a private cloud service** (Modal, ADR-0017), for clinics with connectivity.

## N-ATLaS integration
- **Note model:** N-ATLaS 8B (`NCAIR1/N-ATLaS`), fine-tuned with QLoRA on antenatal records in Yorùbá, Pidgin and English (ADR-0024; run C-fs, chosen on dev and pilot data only). It is merged, quantised to 4-bit (imatrix Q4_K_M, 4.9 GB) and served by llama.cpp on the CPU.
- **Speech:**
  - `NCAIR1/Yoruba-ASR`, fine-tuned on Yorùbá speech;
  - `NCAIR1/NigerianAccentedEnglish`, fine-tuned on Pidgin and used as-is for English (ADR-0026);
  - int8 builds of all three (ADR-0032).
- **Model repos on Hugging Face:** `malikbello/N-ATLaS-Health-ANC-Scribe-GGUF-Powered-by-Awarri` and `malikbello/N-ATLaS-ASR-Health-{Yoruba,Pidgin}-Powered-by-Awarri`, under the N-ATLaS Terms.

## Try it
- **Clinic hub on a laptop, with the phone app:** takada-app `docs/operations.md` (Docker Desktop, one command, then pair a phone with a code).
- **The API on its own:**
  ```bash
  pip install -e ".[dev,data]"
  PHC_ENV=dev uvicorn phc_scribe.api.app:create_app --factory --app-dir serve
  # http://127.0.0.1:8000/docs  (OpenAPI: docs/openapi.v1.json, guide: docs/api.md)
  ```
- **Checks:** `./scripts/ci_local.sh` (lint, types and tests, the same as CI).

## Repository map
| Path | What |
|---|---|
| `serve/phc_scribe/` | The /v1 API: extraction, speech, rules, grounding, polarity and salvage checks |
| `bench/` | Benchmark harness, metrics, fine-tuning and evaluation code |
| `rules/`, `schema/` | Danger-sign rules and visit guide; the encounter schema and vocabulary |
| `deploy/` | API image; Modal jobs for training, quantisation and evaluation |
| `review-app/` | The web app the nurses used to sign off the clinical content and label the benchmark |
| `docs/` | Architecture, eval plan, results, decision records (`docs/adr/`), API guide |
| `results/` | Every reported number, as JSON (no patient text) |

## Limits, said plainly
- **Danger signs are still missed:** about 1 in 3 in Yorùbá statements and 1 in 4 in Pidgin (S5). That is why the nurse confirms every record and the visit guide prompts the danger-sign questions.
- **Recall on real recorded speech is not yet measured.** Real speech has too few danger signs; S4-W measures false alarms.
- **Not yet used in a clinic with real patients.** Validation so far:
  - real speech clips and real antenatal teaching sentences;
  - clinical sign-off of the content by a nurse;
  - test visits recorded on a phone through the full system.

  A clinic pilot needs ethics approval and a data-protection impact assessment (ADR-0033).
- **A draft takes minutes on a laptop CPU,** not seconds. The draft starts by itself when the nurse stops recording, and she carries on with the visit meanwhile.
- **Smaller laptops:** a 3-bit note model was tried and **rejected** on dev data, because it missed too many danger signs (ADR-0032). 8 GB laptops need a distilled model, which is on the roadmap.
- **Hausa and Igbo** speech models are wired in but not evaluated.

## Roadmap
1. **Hardware tiers (ADR-0032):**
   - int8 speech is built and checked (English live; Yorùbá and Pidgin after their test-pool check);
   - next, a distilled 1–3B note model for 8 GB laptops;
   - then phone-only clinics.
2. **Live listening (ADR-0034):** question prompts and quiet danger-sign hints during the visit, from transcripts 20 s at a time.
3. **The phone stays on the clinic Wi-Fi by itself (ADR-0035).**
4. **A clinic pilot** with ethics approval; then Hausa and Igbo.

## Team
- **Malik Bello:** lead; machine learning and engineering
- **Rahmat:** nurse; clinical adviser, clinical sign-off and adjudication of labels
- **Abdullah Oseni:** medical student; annotation
- **Eniola Oluwatosin:** pharmacist; medicines content

## Licensing
- Code licence: to be decided before public release.
- N-ATLaS models and derivatives are governed by the N-ATLaS Terms of Use. See [`NOTICE`](NOTICE).
- Data licences for every benchmark source: [`docs/license-ledger.md`](docs/license-ledger.md).
