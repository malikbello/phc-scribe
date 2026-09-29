# PHC Scribe

**An offline-first AI scribe and safety net for Nigeria's primary-health-care workers, built on N-ATLaS.**

A nurse or community health worker speaks through an antenatal visit in Yoruba or English. PHC Scribe:
- drafts the structured visit record
- checks danger signs against the National Standing Orders using deterministic rules
- prepares the referral note and the monthly NHMIS report

It runs without internet on an ordinary laptop. The health worker reviews and confirms every record.

> Entry for the **National AI Innovation Challenge 2026** (NCAIR / ONDI / FMCIDE): **Problem Statement 03, Sectoral Fine-Tuning: primary healthcare and community health.**

## Why
- Nigeria has **28.7% of the world's maternal deaths** (~75,000 in 2023) and roughly **one doctor per 9,000 people**. Most antenatal care is delivered by nurses, midwives and CHEWs.
- Recording takes **about a third of consultation time**, plus about **9 hours a month** of paper reporting.
- The conversation is in Yoruba, Hausa or Igbo, but the record must be written in English.
- Clinics lack reliable power and internet, so cloud-only tools can't serve them.

## How (summary)
- **Fine-tuned N-ATLaS** (QLoRA) for antenatal visit documentation, with schema-constrained, evidence-grounded outputs
- **Rules decide danger signs; the model only documents.** Every flag cites its protocol source.
- **One API, many runtimes:** cloud GPU (vLLM) and offline laptop/edge CPU (llama.cpp)
- **Offline-first PWA**, an event-sourced record store, and FHIR R4 + DHIS2 interoperability
- **Eval-first:** a pre-registered benchmark (520+ real-data items) against base N-ATLaS, with confidence intervals

Full design: [`docs/architecture.md`](docs/architecture.md) · decisions: [`docs/adr/`](docs/adr/README.md) · evaluation: [`docs/eval-plan.md`](docs/eval-plan.md)

## Status
🚧 Day 1 of 14: architecture approved; decision records and eval plan committed. Gate 1 groundwork is in: encounter schema v0.1, the danger-sign rules engine, grounding checks, the rung-1 baseline, the benchmark harness with CIs, and CI. The data audit is waiting on network access. See [`docs/status.md`](docs/status.md).

## Development
```bash
pip install -e ".[dev,data]"
ruff check . && ruff format --check . && pyright && pytest
python -m bench.harness run --system keyword --items tests/fixtures/smoke_items.jsonl --out /tmp/preds.jsonl
python -m bench.harness score --items tests/fixtures/smoke_items.jsonl --pred /tmp/preds.jsonl
```

## Team
- **Malik Bello:** lead, ML and engineering
- **Clinical adviser:** registered nurse, University College Hospital, Ibadan (to be confirmed)
- **Annotator:** medical student (to be confirmed)

## Licensing
- Code license: to be decided before public release.
- N-ATLaS models and derivatives are governed by the N-ATLaS Terms of Use. See [`NOTICE`](NOTICE).
