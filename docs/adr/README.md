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
| [0015](0015-hf-space-public-api.md) | Host the public API on a free Hugging Face Space; defer GPU serving | Accepted |
| [0016](0016-licence-clean-benchmark-data.md) | Counted benchmark is real, consented, CC-BY speech data (NigBench-MAMAI); generated notes are a labelled supplement | **Proposed** |
