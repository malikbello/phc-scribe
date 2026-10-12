# Scalability and sustainability

## The unit of deployment: one hub per clinic
- **A clinic needs:**
  - one ordinary laptop (16 GB RAM, no GPU);
  - the nurses' own Android phones or iPhones;
  - the laptop's Wi-Fi hotspot, or a cheap router.
- **No internet is needed for a visit, and there is no cloud bill.** The internet is used once, to install the models, and optionally to sync a second copy of the records.
- **Setup is one command** (Docker Compose) plus pairing each phone with a code ([takada-app `docs/operations.md`](https://github.com/malikbello/takada-app/blob/main/docs/operations.md)).
- **The models are about 7 GB with fp32 speech, or about 5.6 GB with int8.** On clinic internet at 0.8 MB/s that is 2–3 hours, so a clinic should be installed from a USB drive (planned).

## Capacity, measured on the reference laptop (i7-8665U, 16 GB)
| Step | Time |
|---|---|
| Speech to text, 20 s recording | 56 s fp32; **6 s int8** |
| Note draft (fine-tuned N-ATLaS 8B, 4-bit) | **about 2 min** at the median, 4 min at p95; about 7 min for the first draft after start-up |
| Danger-sign rules, guide, sync | instant, on the phone |

- **Throughput:** drafts run in the background while the nurse carries on. One worker handles roughly **15–25 visits an hour**, an estimate from these times until the load test.
- **Danger-sign alarms never wait for the AI:** the rules run on the phone, offline.

## Hardware tiers (ADR-0032)
| Tier | Hardware | Note model | Speech | Status |
|---|---|---|---|---|
| 1 | 16 GB laptop | 8B 4-bit (4.9 GB) | int8 (1.9 GB peak, all three languages) | **measured** |
| 2 | 8 GB laptop | a distilled 1–3B student of the fine-tuned model | int8 | speech done. A **3-bit 8B was tested and rejected:** dev danger-sign recall fell from 48.6% to 35–41% |
| 3 | phone only | the distilled student at 4-bit | a small int8 model | roadmap |

**Every step brings its own evidence:** it is chosen on dev data and confirmed on a fresh pre-registered test, the same discipline as v1.

## Adding languages and clinical content
- **A language** needs two things:
  - a speech fine-tune: the ADR-0026 recipe took about 50 minutes per language on one free T4 GPU;
  - training statements for the note model.
- **The danger-sign rules work on concepts, not words,** so they carry over unchanged. Hausa and Igbo speech models are already wired in.
- **Clinical content** (danger-sign rules, visit guide, medicines) lives in reviewed YAML files with their sources. Clinicians sign it off in the review app before it ships.

## Cost of building and maintaining it
- **Training and evaluation ran on free tiers:**
  - the note model's fine-tuning runs took about 12 GPU hours (ADR-0024);
  - the speech fine-tunes took 4–5 GPU hours (ADR-0026);
  - the int8 conversion and checks used a few CPU hours.
- **Updates reach a clinic as new hub images,** and phones show an "Update available" button. Records sync as an append-only log, so an update never loses one.
- **Monitoring:** health and readiness endpoints (`/healthz`, `/readyz`), and structured logs with no clinical text.

## Data protection (ADR-0033)
- **Consent:** recording only after the woman agrees.
- **Pseudonymous patients:** an ANC card number or initials, never a full name.
- **Retention:**
  - recordings and full transcripts are deleted 7 days after the record is confirmed;
  - nothing leaves the clinic by default.
- **Before a real pilot:** disk encryption on the hub, and a data-protection impact assessment with the facility.

## Licence constraints that shape scale
- **N-ATLaS Terms of Use:** derivatives carry "Powered by Awarri", and deployments are capped at **1,000 active end-users per rolling 30 days** without a commercial licence from Awarri Technologies. A pilot fits within the cap; a state roll-out needs that licence.
- **Benchmark data sources** keep their licences (`docs/license-ledger.md`).

## Path to scale
1. **Pilot:** 1–3 primary health centres, with ethics approval. Measure time saved per visit, how often nurses correct the draft, and danger signs caught or missed against a clinician's review.
2. **State:** one hub per PHC through the state primary health care board; then DHIS2/NHMIS reporting from the confirmed records (planned).
3. **Smaller hardware and phone-only clinics** (Tiers 2–3), then live listening during the visit (ADR-0034).
