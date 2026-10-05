# Architecture decision records

Format: context → decision → consequences. A decision changes only through a new ADR that supersedes it.

| # | Decision | Status |
|---|---|---|
| [0001](0001-ps3-sectoral-fine-tuning.md) | Enter NAIC 2026 under PS3 (Sectoral Fine-Tuning) | Accepted |
| [0002](0002-documentation-not-patient-qa.md) | Clinical documentation (structured extraction), not patient Q&A | Accepted |
| [0003](0003-rules-decide-model-documents.md) | Deterministic rules decide danger signs; the model only documents | Accepted |
| [0004](0004-constrained-decoding-and-grounding.md) | Schema-constrained decoding plus evidence grounding | Accepted |
| [0005](0005-one-api-many-runtimes.md) | One API contract, many runtimes | Accepted |
| [0006](0006-yoruba-first.md) | Yoruba first, English alongside | Accepted |
| [0007](0007-no-hardware-zero-budget.md) | No purchased hardware and a $0 cash budget for NAIC | Accepted |
| [0008](0008-event-sourced-records-outbox-sync.md) | Append-only, event-sourced record store with outbox sync | Accepted |
| [0009](0009-evaluate-what-we-ship.md) | Evaluate the artefact we ship | Accepted |
| [0010](0010-modular-monolith.md) | Modular monolith plus separately scaled AI services | Accepted |
| [0011](0011-health-data-standards.md) | Standards: WHO ANC DAK, LOINC, ICD-11, FHIR R4 with Provenance | Accepted |
| [0012](0012-hfr-tenancy.md) | Tenancy keyed to the Nigeria Health Facility Registry hierarchy | Accepted |
| [0013](0013-antenatal-module-one.md) | Antenatal care is clinical module one | Accepted |
| [0014](0014-offline-first-pwa.md) | Offline-first PWA frontend with enforced performance budgets | Accepted |
| [0015](0015-hf-space-public-api.md) | Host the public API on a free Hugging Face Space; defer GPU serving | Superseded by 0017 |
| [0016](0016-licence-clean-benchmark-data.md) | Counted benchmark is real, consented, CC-BY speech data (NigBench-MAMAI); generated notes are a labelled supplement | Accepted |
| [0017](0017-modal-for-the-cloud-api.md) | Serve the cloud API on Modal, private until submission | **Proposed** |
| [0018](0018-wazobiaspeech-fallback-benchmark.md) | If NigBench-MAMAI is refused, the counted benchmark is WazobiaSpeech health speech | Accepted |
| [0019](0019-uyo-records-rules-check.md) | Check the danger-sign rules on real Uyo antenatal records | Accepted |
| [0020](0020-antenatal-orientation-speech.md) | Antenatal Orientation Speech Dataset: hard negatives, ASR test, phrases | Accepted |
| [0021](0021-teacher-labels.md) | Teacher labels from Llama-3.1-8B for real training speech | Accepted |
| [0022](0022-two-stage-freeze.md) | Freeze the test set in two stages: items first, labels before scoring | Accepted |
| [0023](0023-takada-health-worker-app.md) | Takada health-worker app: own repo; phone + clinic hub + cloud; protocol-driven visit guide; container- and Kubernetes-ready | Accepted |
| [0024](0024-finetuning-recipe.md) | Fine-tuning recipe: data first (concept audit, rare-sign phrase bank, ASR two-view), safety-weighted SFT, bounded output, on-policy DPO if needed, scaled merge, imatrix Q4 | Accepted |
| [0025](0025-committee-triage-labelling.md) | Committee pre-labelling (3 non-Llama open models), humans label a stratified random sample (156 labels after the 4 Oct cut), stratified PPI for the estimates | Accepted |
| [0026](0026-asr-health-finetune.md) | Fine-tune N-ATLaS ASR (Yoruba-ASR; NigerianAccentedEnglish for Pidgin) on WazobiaSpeech train speech; ship only if test WER improves | Accepted; **ships** (test WER −26.3 pts Pidgin, −6.7 pts Yoruba) |
| [0028](0028-synthetic-danger-sign-training-data.md) | In-language synthetic training statements by base N-ATLaS (rule checks + round-trip check) so every danger sign has training examples; the phrase bank is set aside while S5 is a test | Accepted |
