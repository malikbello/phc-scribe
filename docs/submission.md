# NAIC 2026: where to find everything

**PHC Scribe, with the Tákàdá app.** Problem Statement 3, Sectoral Fine-Tuning (primary health care). Track B, Innovation & Enterprise.

## The seven submission components
| Component | Where |
|---|---|
| **1. Working artefact** | **Live demo: https://takada-app.vercel.app** → **Try the AI demo**: record a made-up visit and get the draft from the fine-tuned N-ATLaS on a cloud GPU ([how it works](../README.md#try-it)).<br>**This repository:** the fine-tuned models, the benchmark and the `/v1` API.<br>**[`malikbello/takada-app`](https://github.com/malikbello/takada-app):** the phone app and the offline clinic hub.<br>**Four model repos on Hugging Face** (gated, approved automatically; see the [README](../README.md#n-atlas-integration)). |
| **2. N-ATLaS integration** | Both N-ATLaS models are fine-tuned and run offline together:<br>- **N-ATLaS 8B** writes the record (QLoRA, then 4-bit, on a laptop CPU; [ADR-0024](adr/0024-finetuning-recipe.md), [model card](cards/model-card.md));<br>- **N-ATLaS ASR** hears the visit (Yorùbá and Pidgin fine-tuned, English as is; [ADR-0026](adr/0026-asr-health-finetune.md)).<br>The whole system was run end to end on the hub ([benchmark report §7](benchmark-report.md#7-on-a-clinic-laptop)). |
| **3. Real-world validation** | **[Benchmark report](benchmark-report.md):**<br>- pre-registered, against base N-ATLaS, scored once on frozen sets;<br>- **1,024 real examples:** 570 real Yorùbá and Pidgin health speech clips, and 454 real antenatal teaching sentences;<br>- 600 real speech clips for speech recognition;<br>- a nurse's clinical sign-off of the content and labels;<br>- test visits recorded on a phone through the clinic hub. |
| **4. Technical documentation** | [Architecture](architecture.md) · [API guide](api.md) ([OpenAPI](openapi.v1.json)) · [Running a clinic hub](https://github.com/malikbello/takada-app/blob/main/docs/operations.md) · [Decision records](adr/README.md) · [Scalability and sustainability](scalability-and-sustainability.md) · [Model card](cards/model-card.md) · [Dataset card](cards/dataset-card.md) · [Error taxonomy](error-taxonomy.md) |
| **5. Video demonstration** | Linked in the submission form (3–5 minutes, end to end). |
| **6. Team profile** | [README, Team](../README.md#team): a nurse, a medical student, a pharmacist and an engineer. |
| **7. Registration** | Valid ID, in the submission form (Track B). |

## The judging criteria, and the evidence
1. **Working artefact and technical rigour:**
   - the system runs offline on a 16 GB laptop with no GPU;
   - every main result was pre-registered and scored once on frozen test sets ([ADR-0022](adr/0022-two-stage-freeze.md));
   - CI runs lint, type checks, tests and a secret scan on every change to both repositories.
2. **N-ATLaS integration:**
   - the language model and the speech models are both fine-tuned and served together;
   - recordings become records with no internet.
3. **Real-world validation:**
   - on 570 real speech clips, false alarms halve, from 26.5% to 13.2% (−13.3 points [−15.9, −11.0]);
   - more danger signs are found than by base N-ATLaS in Yorùbá, Pidgin and English;
   - Pidgin speech-recognition errors halve, from 51.1% to 24.8%.
4. **Impact potential:**
   - antenatal danger signs are checked on every visit, in the language of the visit;
   - recording is consented, and recordings are deleted after 7 days ([ADR-0033](adr/0033-retention-of-recordings-and-transcripts.md)).
5. **Scalability and sustainability:**
   - one hub per clinic, with hardware tiers ([ADR-0032](adr/0032-model-footprint-hardware-tiers.md));
   - int8 speech is already live;
   - a cloud service for connected clinics ([scalability](scalability-and-sustainability.md)).
6. **Team capability:** the clinical content and labels were written and checked by the team's nurse, medical student and pharmacist ([README, Team](../README.md#team)).

## Limits
Read the [README's limits](../README.md#limits-said-plainly) and the [error taxonomy](error-taxonomy.md) next to the results:
- danger signs are still missed;
- recall on real recorded speech is not yet measured;
- there has been no clinic pilot yet.
