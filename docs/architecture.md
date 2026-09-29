# PHC Scribe: solution architecture (v3)

Status: **Approved by Malik Bello, 29 Sept 2026.** Changes go through a decision record in `docs/adr/`.

Repo: `phc-scribe` (private until submission). Agent/product name: **pending Malik's pick** (Part C, section C1). It is an AI scribe and safety net for primary-health-care workers, built on a fine-tuned N-ATLaS and entered under **PS3 Sectoral Fine-Tuning, primary healthcare and community health**.

---

## What "the way a mature lab team would build it" means here

Mature ML teams at frontier AI labs and big tech don't win by building more components. They win on **rigour where it matters**:
- **Evals come first.** The evaluation is the spec, written before any training.
- **Ship what you evaluated.** The number reported is the number of the exact artefact deployed.
- **The model cannot do harm on its own.** Guardrails, grounding and a human sit between model output and consequences.
- **Everything is reproducible.** Pinned configs, versioned data, tracked experiments.
- **Every decision is written down.** Decision records, model card, datasheet, hazard log.
- **Scope is cut ruthlessly** to what the deadline can carry at that quality bar.

v1 had the right shape but was light on all six. v2 fixes that. The changes from v1:

| # | Area | v1 | v2 (mature-team standard) |
|---|---|---|---|
| 1 | Process | Build, then evaluate | **Eval-first.** The evaluation plan and success criteria are committed to the repo (timestamped) **before** any training. |
| 2 | Schema | Symptom/danger-sign lists | **Clinical assertion status** on every finding: present / absent / possible / historical / not-mentioned. This is standard clinical NLP; it handles negation ("no bleeding") and history ("bled in her last pregnancy"). |
| 3 | Grounding | "Evidence spans" | Spans are **machine-verified** against the transcript. Any ungrounded field is dropped and the record is flagged "needs review". Grounding rate is a tracked metric. |
| 4 | Statistics | Single scores | **95% confidence intervals** (bootstrap) and **paired significance tests** (paired bootstrap; McNemar for danger-sign detection), plus effect sizes. |
| 5 | Gold labels | Double annotation | Written **annotation guidelines**, **inter-annotator agreement** (Cohen's κ) on an overlap set, and a nurse-adjudication protocol |
| 6 | Baselines | Base N-ATLaS | A **baseline ladder**: rules/keyword baseline → Llama-3-8B-Instruct (N-ATLaS's own parent) → base N-ATLaS zero-shot → few-shot → **our fine-tune**. The parent comparison shows what N-ATLaS itself contributes. |
| 7 | What ships | Evaluate the adapter | **Evaluate the quantized Q4 model that actually ships**, plus the full-precision one, and report the quantization loss |
| 8 | Leakage | Frozen test split | **Group-wise splits by source note**, so an English note and its Yoruba translation never land on different sides. Train/test dedupe and near-duplicate checks. |
| 9 | Safety eval | Not in v1 | A **red-team set**: negations, hedges, history vs current, another person's symptoms, mixed-language numbers, ASR noise, and instructions hidden inside a transcript |
| 10 | Regression | Not in v1 | **Capability regression check:** the fine-tune must not wreck N-ATLaS's general Yoruba ability (small held-out general set) |
| 11 | Governance | Model card | **Model card + benchmark datasheet + clinical hazard log** (a lightweight version of how regulated health-software teams track risk) + a license/consent ledger per data source |
| 12 | Engineering | Scripts | Decision records, **CI** (lint, types, tests, secret scan, smoke-eval on every change), pinned environments, a tracked experiment log, and a versioned API and schema |

---

## 0. Design inputs

| Constraint | Consequence |
|---|---|
| **No purchased hardware; $0 budget** | Training on Kaggle (free, about 30 GPU-h/week). Online API on Modal ($30/month free credits, scales to zero). Offline node on Malik's laptop. |
| **Laptop: Dell Latitude 5400, Core i7-8665U (4 cores / 8 threads, AVX2), 16 GB RAM, Intel UHD 620 (no usable GPU), Windows 11 + WSL2, Ollama already installed** | Runs the Q4 8B model and speech recognition on CPU. Expect roughly 2–5 tokens/s generation, to be measured on day 1–2. |
| ⚠️ **Laptop disk: only 8.3 GB free** | **Blocker.** Malik must free **≥25 GB** before day 2: model (about 5 GB), speech models (about 1 GB), WSL/Python environments, working data. The 16 GB full-precision weights **never** touch the laptop; conversion happens on Kaggle. |
| Team of 3: Malik (lead, ML/eng, native Yoruba), UCH nurse (clinical adviser/adjudicator), medical student (annotator) | Covers the 2–5 team-size rule and clinical credibility |
| PS3 rules | An N-ATLaS derivative; 500+ real-data benchmark vs base; a documented API |
| N-ATLaS license | A derivative carries the same terms, attribution, "Powered by Awarri", and the 1,000 active-user cap |
| 14 days | Anything not needed for a rigorous PS3 entry is cut (section 10) |

---

## 1. Principles (unchanged from v1, now enforced in code)
1. **Safety never waits for AI.** Danger-sign flags come from deterministic rules. The AI only drafts documentation.
2. **The model fills forms, it never advises.** Output is decoded against a JSON schema and evidence-grounded. Rejected fields go to a human.
3. **The human confirms every record.** Confirmed records are immutable; edits are recorded as amendments.
4. **One API, many runtimes** (cloud GPU, laptop CPU, future edge box). It is model-agnostic behind an adapter.
5. **Ship what you evaluated.** The quantized artefact that runs is the one benchmarked.

---

## 2. System overview

```
 Phone / laptop browser (web UI)          Developer (3rd-party integrator)
          │                                          │
          └──────────────┬───────────────────────────┘
                         ▼  HTTPS or local hotspot
 ┌─────────────────────── Scribe API  /v1  (FastAPI, OpenAPI spec) ───────────────────────┐
 │ request-id · API key · rate limit · PHI-redacted structured logs · metrics             │
 │                                                                                        │
 │  /v1/transcribe ─► ASR adapter ─► official NCAIR1 Whisper-Small (yo, en) via CT2 int8  │
 │                                                                                        │
 │  /v1/extract ─► Extraction pipeline                                                    │
 │      1. normalise transcript (Unicode NFC, Yoruba diacritics kept + folded copy)       │
 │      2. model adapter ─► fine-tuned N-ATLaS (schema-constrained decoding)              │
 │      3. schema validation (Pydantic, encounter schema v0.x)                            │
 │      4. grounding check: every field's evidence span must exist in the transcript     │
 │      5. value checks: physiological ranges (e.g. BP 50–300), unit normalisation       │
 │      6. anything failing 3–5 ─► dropped + record marked NEEDS_REVIEW                   │
 │                                                                                        │
 │  /v1/check ─► Rules engine (versioned YAML rules, each cites NSO/WHO source + tests)   │
 │  /v1/records ─► append-only event store (SQLite): draft → confirmed → amended          │
 │  /v1/reports/nhmis ─► monthly summary export (CSV, DHIS2 dataValueSets JSON)           │
 │  /v1/chat/completions ─► OpenAI-compatible passthrough (for other developers)          │
 │                                                                                        │
 │  Model adapter ─┬─ GPU: vLLM + LoRA on Modal (cloud, scale-to-zero)                   │
 │                 └─ CPU: llama.cpp server, GGUF Q4_K_M (laptop / future edge box)       │
 └────────────────────────────────────────────────────────────────────────────────────────┘

 Offline ML pipeline (Kaggle + repo):
 data audit → de-identify → license ledger → group split → annotate (IAA) → freeze test
 → generate/filter training data → QLoRA (config-driven, tracked) → merge → GGUF Q4
 → eval ladder (fp16 + Q4) with CIs → red-team + regression → model card / datasheet
```

Every response carries `model_version`, `schema_version`, `rules_version`, `request_id` and the N-ATLaS attribution string. Any output can be traced to the exact artefacts that produced it.

---

## 3. Encounter schema v0 (clinical NLP standard)

Scope is decided by the **data audit** (Gate 1). The target is **antenatal care (ANC)**. If the real notes available turn out to be mostly general outpatient visits, the fallback is a **general PHC encounter core** plus the danger-sign module.

- **Findings** (symptoms and danger signs): each has
  - a `concept` from a controlled vocabulary aligned to the National Standing Orders
  - an `assertion` ∈ {present, absent, possible, historical, not_mentioned}
  - an `evidence` span (character offsets + text)
- **Vitals:** BP systolic/diastolic, temperature, weight, pulse. Each with value, unit and evidence, and range-checked.
- **ANC fields:** gestational age (weeks), gravida/parity, visit number, tests done (malaria RDT, urinalysis, Hb), supplements/medications given
- **Disposition:** referral (y/n, destination), next visit date
- **Referral summary:** short English text, **for human review only**, never auto-sent
- Versioned with semver (`encounter.v0.1.json`). Breaking changes bump the major version.
- **Standards alignment (production requirement):**
  - data elements follow the **WHO SMART Guidelines ANC Digital Adaptation Kit** (WHO's software-neutral ANC data dictionary + decision logic, already used in national ANC systems in Rwanda and Zambia)
  - vitals are coded in **LOINC**, conditions in **ICD-11** (both free to use). SNOMED CT is avoided because it needs a country license.
  - export is **HL7 FHIR R4** (Part B)

**Rules engine contract:** any danger sign with assertion `present` **or** `possible` raises a flag ("possible" is flagged too: safety-first). Every rule has unit tests the nurse has reviewed.

---

## 4. Evaluation plan (written first, committed before training)

### 4.1 Benchmark: PHC-Scribe-Bench v0 (≥520 test items)
| Stratum | Size | Source | Notes |
|---|---|---|---|
| S1 English real notes | ~260 | African Medical Records (real Nigerian clinical notes, CC BY 4.0 per its card), after the data audit and de-identification check | Gold JSON |
| S3 Yoruba translations of S1 | ~260 | Translated by Malik, with clinical meaning checked by the nurse | **Same group ID as the English original**, so the pair always stays in the same split |
| R Red-team (reported separately) | ~60 | Constructed adversarial cases | Labelled as constructed. Not counted toward the 500 real items. |
| S2 Real Yoruba dictations | later | Nurses, after UI/UCH ethics approval | Acceleration phase |

**Enrichment:** sampling is stratified so that **≥30% of items contain a danger sign**. Otherwise the safety metric's confidence interval would be too wide to mean anything.

### 4.2 Gold-label process
- Annotation guidelines v0, reviewed by the nurse
- Malik + the medical student each label a **60-item overlap set**. Agreement is measured with Cohen's κ per field. Target κ ≥ 0.7; below that, the guidelines get revised.
- Disagreements go to the nurse for a final decision. Everything is logged.

### 4.3 Metrics (per stratum, per language, per field, with 95% bootstrap CIs)
- **Primary (safety):** danger-sign **recall** on present/possible
- **Co-primary:** field-level micro-F1 over (concept, assertion) pairs
- **Secondary:**
  - false-alarm rate
  - ungrounded-field (hallucination) rate
  - numeric exact-match (BP, gestational age)
  - schema-valid rate
  - latency and prompt-token count on the **laptop CPU** and on GPU
- **Robustness:** red-team pass rate; score under simulated ASR noise
- **Regression:** a small held-out general Yoruba set scored for base vs fine-tune
- **Diacritics:** every Yoruba metric reported with and without tone-mark folding

### 4.4 Baseline ladder
All rungs get the same schema-constrained decoding, so the comparison measures content, not formatting.
1. Rules/keyword baseline (no ML)
2. Llama-3-8B-Instruct (N-ATLaS's parent), few-shot
3. Base N-ATLaS zero-shot
4. Base N-ATLaS few-shot
5. **Fine-tuned N-ATLaS, full precision**
6. **Fine-tuned N-ATLaS, Q4_K_M (the artefact that ships)**

### 4.5 Pre-registered success criteria (Gate 2)
The exact thresholds are fixed after the 30-item pilot and **before training**. They are committed with a timestamp.
- **Primary:** fine-tune (Q4) beats base N-ATLaS few-shot on danger-sign recall, with the **lower bound of the 95% CI of the difference > 0** (paired bootstrap), in English and in Yoruba.
- **Co-primary:** the same test on micro-F1.
- **Guardrails:** false-alarm rate is no worse than base by more than a pre-set margin; general-Yoruba regression is within a pre-set margin.
- If a criterion fails, **we report it honestly** rather than moving the goalposts.

---

## 5. Data engineering
- **Data audit first (day 1–2):** what AMR actually contains (visit types, size, language, any identifiers, license and consent statements). Nothing is designed on assumptions.
- **De-identification:** a rule-based scrub (names, phone numbers, addresses, dates shifted) plus a manual check of every test item.
- **License/consent ledger:** one row per source (license, consent basis, allowed uses), committed to the repo.
- **Versioning:** dataset manifests with content hashes. Raw clinical text is **never committed to git**. It lives in a private Kaggle dataset / HF dataset with pinned revisions.
- **Splits:** group-wise by source note; exact and near-duplicate removal across splits (hash + n-gram overlap). The test set's hash is committed before training.
- **Training data:**
  - real train-split notes
  - generated narratives from schema-sampled cases, written in English and Yoruba (Malik spot-checks the Yoruba), filtered by schema validation, grounding and dedupe
  - generators limited to models whose terms permit this use; no closed-API outputs
  - generated data is never in the test set, and every example is tagged by origin

---

## 6. Training
- **Method:** QLoRA on `NCAIR1/N-ATLaS` (4-bit base, LoRA r=16–32 on attention + MLP), using N-ATLaS's own chat template. Kaggle T4.
- **Short prompts by design:** the fine-tune learns the schema, so its prompt drops from about 2,500 tokens (schema + few-shot) to about 400. On a CPU, reading the prompt is the slow part, so this should roughly halve laptop latency. That makes it a **measurable edge benefit of fine-tuning**, not just an accuracy one.
- **Reproducibility:** YAML configs, fixed seeds, pinned library versions, an MLflow run log. The results JSON is committed per run.
- **Budget:** at most 3 main runs + 1 ablation (with vs without generated data) within the free Kaggle quota.
- **Artefacts:** LoRA adapter → merged model → GGUF Q4_K_M, each with a SHA-256 checksum. Published gated on HF under the N-ATLaS terms ("… Powered by Awarri").

---

## 7. Serving and operations
- **API contract first:** an OpenAPI spec for `/v1`, versioned schema, idempotency keys on record writes, a consistent error envelope, request IDs.
- **Runtimes:**
  - **Laptop (offline node):** llama.cpp server (Q4_K_M, prompt-prefix caching, schema grammar) + faster-whisper (int8), run under WSL2. Ollama (already installed) is the fallback runtime.
  - **Cloud:** Modal, vLLM + LoRA, scale-to-zero, for judges and developers.
- **Observability:** structured JSON logs with clinical text **redacted**, plus p50/p95 latency, token counts, schema-valid rate, grounding-failure rate and NEEDS_REVIEW rate per model version.
- **Security:**
  - hashed API keys, rate limiting, TLS on cloud
  - secrets only in Kaggle/Modal secret stores, never in the repo (CI secret scan)
  - pinned dependencies with a vulnerability audit in CI
- **Data protection (NDPA 2023):**
  - de-identified by default
  - audio deleted after confirmation
  - on the offline node, data never leaves the laptop
  - append-only audit trail of drafts, confirmations and amendments

---

## 8. Clinical safety case (lightweight hazard log)

Reviewed and signed off by the nurse. Examples:

| Hazard | Cause | Controls | Residual |
|---|---|---|---|
| Missed danger sign | Model misses or misreads a symptom | Tap checklist on the same screen (rules, no AI); "possible" is flagged too; recall is the primary metric | Worker still judges clinically; the tool is an aid |
| Invented value (e.g. BP) | Hallucination | Grounding check drops unsupported fields; range checks; human confirmation | Low |
| Wrong assertion ("no bleeding" read as bleeding) | Negation errors | Assertion status in the schema; red-team negation cases | False alarms preferred over misses |
| Over-trust (automation bias) | Worker accepts the draft blindly | Evidence highlighted per field; unconfirmed fields visually marked; "documentation aid" labelling | Monitored in the pilot |
| Privacy breach | Identifiers stored or logged | De-identification, log redaction, local-only mode | Low |

---

## 9. Where it runs (no purchases)
| Tier | Where | Internet | Purpose |
|---|---|---|---|
| Cloud GPU | Modal | Online | Judges' API, benchmark runs |
| **Offline node** | **Malik's laptop**, phones on its Wi-Fi hotspot | **None** | Offline demo (video), pilot |
| Future edge box | Mini-PC/Jetson + solar, paid for by the buyer | None | State pilot and national rollout; same image as the laptop |

**Honest latency expectation on this laptop:** about 1–2 minutes per visit record for the fine-tune, and roughly double for base few-shot. Measured on day 1–2. That's acceptable because documentation is asynchronous and danger-sign flags are instant (rules). The video will show real timing.

---

## 10. Scope and deliberate non-goals

A mature team would cut these for a 14-day entry:
- no microservices, Kubernetes or custom training framework (one FastAPI service, standard tools)
- no LLM-as-judge for structured fields (exact metrics are better)
- no native Android app, no live DHIS2 push, no modules beyond ANC/danger signs
- ~~no offline phone queue~~ → **now in scope** (Part B): a production-grade offline-first client is a one-way-door decision, so it's built from day one.
- no treatment recommendations, ever

**Scale path** (unchanged from v1): NAIC entry → acceleration-phase pilot in Ibadan (S2 with ethics approval) → state pilot, with hardware funded by the state or a donor → national, via an Awarri commercial license and the procurement pathway.

---

## 11. Repo layout (`phc-scribe`, private until submission)
```
docs/        architecture, adr/ (decision records), eval-plan, annotation-guidelines,
             model-card, datasheet, hazard-log, api, license-ledger
schema/      encounter.v0.x.json, vocab/ (NSO-aligned concepts)
rules/       danger_signs.v0.yaml + tests (nurse-reviewed)
bench/       harness, metrics, bootstrap/McNemar stats, reports/
data/        manifests + hashes only (no raw clinical text in git)
train/       configs/, Kaggle notebooks, merge + GGUF scripts
serve/       FastAPI app, runtime adapters (llama.cpp, vLLM), Modal app
web/         minimal capture/review UI
tests/       unit, contract, rules golden tests, smoke-eval
.github/     CI: ruff, pyright, pytest, secret scan, dependency audit, smoke-eval
```

**Decision records to write up front:**
1. PS3 over PS2
2. Extraction, not Q&A
3. Rules decide, the model documents
4. Constrained decoding + grounding
5. One API, many runtimes
6. Yoruba first
7. No purchased hardware
8. Append-only record store
9. Evaluate the shipped quantized artefact

---

## 12. 14-day plan with gates (v3: ML, platform and design tracks run in parallel)
| Days | ML track | Platform track | Design track | Gate |
|---|---|---|---|---|
| 0 (now) | **Malik:** free ≥25 GB disk; Kaggle + Modal accounts; confirm teammates; email organisers; **pick the name** | — | — | — |
| 1–2 | Eval plan + decision records committed; AMR data audit; schema v0 (WHO ANC DAK-aligned); 30-item pilot; baseline ladder | Repo, CI, monorepo skeleton, API contract (OpenAPI), multi-tenant data model | Brand + design tokens + **clickable prototype** of the core flow for Malik and the nurse to review | **Gate 1:** base has fixable failures; the data supports the scope |
| 2–5 | Annotation, agreement check, translations, red-team set, **freeze test set**, fix thresholds | Event store, sync protocol, auth/roles, FHIR mapping | Walkthrough with the nurse (+ colleagues if possible), then iterate | Test set frozen |
| 3–8 | Training data; QLoRA runs; merge; GGUF; eval full precision and Q4; regression check | Extraction pipeline + guardrails + rules engine; runtime adapters | Build the design system + core screens (record → review → confirm → flag) | **Gate 2:** pre-registered criteria |
| 8–11 | Final benchmark report | Cloud control plane on Modal; laptop node; DHIS2 play-server push (stretch); observability | Monthly report screen; accessibility pass (WCAG 2.2 AA); performance budget check on a low-end phone | CI green; a11y + perf budgets met |
| 11–12 | Model card, datasheet | Security review, load test (small), docs | **Usability test with 5 health workers**, System Usability Scale (SUS) score, fix top issues | SUS ≥ 75 target |
| 12–13 | — | Submission package | 3–5 min video | **Submit day 13** |

**Cut lines if behind** (in order): DHIS2 live push → red-team set size → ablation → monthly-report polish → Modal (keep laptop + recorded demo).
**Never cut:** the frozen real-data test set, the statistics, grounding, the rules engine, the offline-first core flow, accessibility basics.

## 13. Decisions log
| Decision | Answer |
|---|---|
| N-ATLaS access | ✅ Granted on all 5 repos (28 Sept) |
| Language | Yoruba first, alongside English |
| Budget | $0 |
| Team | Malik + UCH nurse + medical student (to be confirmed as named members) |
| Repo | `phc-scribe`, private until submission |
| Laptop | i7-8665U / 16 GB / no GPU. **Disk must be freed (≥25 GB).** |
| Scale | **Design for national scale now; build the one-way doors now; deploy at pilot scale** (Part B) |
| Design bar | Premium, research-led, accessible, offline-first (Part C) |
| Architecture | ✅ Approved 29 Sept 2026 |
| Service architecture | Modular monolith + separately scaled AI services (B9, ADR-0010) |
| **Pending** | Agent name (C1) |

---

# Part B: Production scale (designed for all of Nigeria from day one)

**Stance:** design for national scale now, **build every one-way-door decision now**, deploy at pilot scale. Scaling up should be a configuration and procurement change, never a rewrite.

## B1. Capacity model (design headroom; order-of-magnitude estimates, not facts)
| Dimension | Design target | Basis |
|---|---|---|
| Facilities | up to ~30,000 PHCs | FG target of 17,600 revitalised PHCs (one per ward) + headroom for all PHCs |
| Health-worker users | ~150,000 | ~5 per facility |
| Encounters | 100M/year (~385k per working day, peak ~50/s nationally) | ANC alone is roughly 20M visits/year (≈8M births × ~4 visits × coverage). General OPD makes up the rest. |
| AI inference | Mostly **at the edge**; cloud serves connected facilities | If 100% ran in the cloud: ~250 output tokens/encounter → ~800 tokens/s average, about 5–10 GPUs at peak with batched 8B serving. Affordable, but edge-first keeps costs and data local. |
| Sync payload | Text-only events, a few KB/encounter; audio stays local by default | Works over intermittent 2G/3G |

## B2. Production topology
```
 Facility (PHC)                 State / LGA (optional)          National control plane (hosted in Nigeria)
 ┌──────────────────────┐       ┌──────────────────┐            ┌─────────────────────────────────────────┐
 │ Phones (offline PWA) │◄─LAN─►│                  │            │ API gateway · auth (OIDC) · tenancy     │
 │ Edge node (optional):│       │ Regional sync    │◄──sync────►│ Event store (Postgres, partitioned by    │
 │  llama.cpp + ASR +   │──────►│ relay/cache      │   (mTLS)   │   state × month) · object store         │
 │  rules + SQLite +    │ sync  │ (only if needed) │            │ Model serving: vLLM multi-LoRA autoscale│
 │  outbox              │       └──────────────────┘            │ Model registry · eval gates · OTA       │
 └──────────────────────┘                                       │ FHIR façade · DHIS2 connector · HFR sync│
     no node? phones sync straight to the cloud ───────────────►│ Observability (OTel→Prometheus/Grafana/ │
                                                                │   Loki) · audit log · admin console     │
                                                                └─────────────────────────────────────────┘
```

## B3. One-way doors: built now (NAIC build includes all of these)
| Decision | Why it can't be retrofitted | NAIC implementation |
|---|---|---|
| **Tenancy = the real health-system hierarchy** (state → LGA → ward → facility), keyed by **Nigeria Health Facility Registry (HFR) codes** | Every record, permission and report depends on it | Facility enrolment uses HFR codes. Every row carries `tenant_path`. |
| **Event-sourced records** (append-only, immutable, content-hashed; amendments reference the prior event) | The audit trail, sync and clinical record integrity all depend on it | SQLite at the edge / Postgres in the cloud, same schema via SQLAlchemy + Alembic migrations |
| **Sync protocol v1**: outbox pattern, UUIDv7 IDs, idempotent batched uploads, server watermarks, resumable, compressed | Offline-first is the product; bolting it on later breaks data | Phone → node → cloud, all implemented and tested with simulated flaky links |
| **API and schema versioning** (`/v1`, schema semver, rules semver, model version on every response) | Third-party integrators and national systems depend on stable contracts | The OpenAPI spec is the source of truth. Contract tests run in CI. |
| **Interoperability: FHIR R4 export** (Encounter, Observation, Condition, ServiceRequest for referral, and **Provenance**: "AI-drafted by model X, confirmed by worker Y") | Government procurement will require standards; Provenance is how clinical AI stays accountable | FHIR Bundle export endpoint + validation against the base FHIR spec. DHIS2 aggregate export (push to DHIS2's public test server as a stretch goal). |
| **Identity and roles**: health worker, facility in-charge, LGA M&E officer, state admin, national admin, API client | Permissions touch every endpoint | JWT with roles now, designed so an OIDC provider (Keycloak) drops in later. Offline: device enrolment + PIN. Workers linked to their CHPRBN/NMCN registration numbers later. |
| **i18n and accessibility frameworks** | Retrofitting translations and a11y means rewriting every screen | ICU message format. Yoruba + English at launch; Hausa, Igbo and Pidgin as slots. WCAG 2.2 AA from the first component. |
| **Model artefact versioning**: content-addressed, checksummed, signed manifests | OTA updates to thousands of nodes depend on trust in artefacts | Checksums + manifests now; signing in pilot |
| **Observability hooks**: OpenTelemetry traces and metrics, PHI-redacted logs | Can't debug a national fleet without them | OTel SDK in the API; metrics endpoint; dashboards later |

## B4. Two-way doors: designed now, built when scale demands
- Keycloak / national identity integration
- Postgres partitioning and read replicas
- Regional relays
- Fleet OTA with **staged rollouts** (5% canary → 25% → 100%, automatic rollback on metric regression)
- vLLM **multi-LoRA** serving (one base, adapters per language/module)
- Grafana fleet dashboards
- Hosting in a **Nigerian data centre**, as expected by NDPA transfer rules and government procurement
- Pen-test + OWASP ASVS L2 review before the state pilot
- Play Store packaging via a Trusted Web Activity

## B5. Model platform at scale (the data flywheel)
- **Release gates:** every candidate model must pass the frozen benchmark, the red-team set and the regression set before release. Staged rollout to nodes; shadow mode in new states.
- **Online quality signals:**
  - per-field human **edit rate** (corrections are free labels)
  - NEEDS_REVIEW rate
  - danger-sign override rate
  - all sliced by language, state and model version
- **Flywheel:** consented, de-identified confirmed records → new training data → retrain on a fixed cadence → gated release. Governed by the license/consent ledger.
- **Drift monitoring:** by language, dialect region and facility type.

## B6. SLOs (pilot → national)
| SLO | Pilot | National |
|---|---|---|
| Rules danger-sign check on device | < 100 ms, 100% offline | same |
| Cloud extraction p95 | < 15 s | < 10 s |
| Edge extraction p95 (reference hardware) | < 3 min (laptop) | < 60 s (edge box) |
| API availability | 99.5% | 99.9% |
| Sync completion after connectivity returns | 99% within 24 h | 99.9% within 24 h |

## B7. Security and compliance
- A STRIDE threat model doc
- TLS 1.3 everywhere; mTLS between node and cloud
- Encryption at rest: SQLCipher on nodes; on the phone, WebCrypto with a PIN-derived key
- Least-privilege roles and an immutable audit log
- Secrets only in managed stores
- SBOM + dependency audit in CI
- NDPA 2023 compliance: data minimisation, retention policy, lawful basis, and a data protection impact assessment (DPIA) before the pilot

## B8. Production tech stack
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, Postgres (cloud) / SQLite (edge), OpenTelemetry
- **AI runtime:** vLLM (cloud GPU) and llama.cpp (edge CPU) behind one adapter; faster-whisper for ASR
- **Frontend:** TypeScript, **Preact + Vite** (React API, ~4 KB runtime, for cheap phones), Workbox service worker, Dexie (IndexedDB), FormatJS (ICU i18n)
- **Infra:** Docker Compose for the edge node; Modal (code-defined) for the NAIC cloud; Terraform when moving to a Nigerian data centre
- **Quality:** ruff, pyright, pytest, Playwright end-to-end tests, axe-core accessibility checks in CI, Lighthouse performance budgets in CI


## B9. Service architecture: modular monolith, split on evidence (ADR-0010)
- **One deployable API service**, with strict internal modules: `records`, `sync`, `extraction`, `rules`, `reporting`, `identity`, `interop`.
  - Each module owns its tables and exposes an interface.
  - **No module reads another module's tables.** Modules talk through interfaces and domain events.
- **Separately scaled services, only where hardware or load really differs:**
  - model serving (vLLM on GPU; llama.cpp on CPU)
  - speech-recognition workers
  - the static web client
- **Why not microservices now:**
  - one engineer, so no team-autonomy benefit
  - the edge node is a single offline machine
  - clinical records need one consistent transaction and one audit trail
- **Split triggers:** a module is extracted into its own service only when at least one holds:
  1. a separate team owns it
  2. its load profile diverges sharply (e.g. national DHIS2/FHIR interop)
  3. it needs its own security boundary (e.g. identity moving to Keycloak)

---

# Part C: Product and experience design (premium, research-led)

## C1. Name for the agent (pick one; a quick web check found no clashes, but a formal CAC/trademark/domain check is still needed)
| Name | Language / meaning | Why | Watch-outs |
|---|---|---|---|
| **Àkọsílẹ̀** ("Akosile") | Yoruba: *the written record; what is written down* | Says exactly what it produces. Easy to say: ah-kaw-SEE-leh. Good tagline: *"You speak. Àkọsílẹ̀ writes."* | Yoruba-first; fine for national use with a clear tagline |
| **Olùgbọ́** ("Olugbo") | Yoruba: *the listener* | A warm persona for a voice-first agent: *"Olùgbọ́ listens, so you can care."* | "gb" is hard for non-West-African ears (irrelevant for Nigerian judges and users) |
| **Magatakarda** | Hausa: *scribe, court secretary* | A historic, dignified role; strong for the national and northern rollout | Long; Yoruba-first launch |

Rejected because they're already used in Nigeria: **Akọ̀wé** (an edtech credentials startup) and **Ìtọ́jú** (several health apps, including an AI maternal-health companion).
Malik (a native speaker) to confirm the tone marks.

## C2. Who we design for (research-led, not assumed)
- **Primary persona:** an ANC nurse or midwife at a busy PHC in Ibadan.
  - 30–60 antenatal clients on clinic days; paper registers
  - a mid/low-end Android phone
  - switches between Yoruba and English mid-sentence
  - often standing, interrupted, in noisy rooms, sometimes in bright light, sometimes gloved
- **Secondary personas:** a CHEW in a rural LGA (lower digital confidence); the facility in-charge (reviews, signs off monthly reports); the LGA M&E officer (consumes reports).
- **Method:**
  - 30-minute contextual interviews with the UCH nurse + 2–4 colleagues
  - a journey map (paper today vs Àkọsílẹ̀ tomorrow)
  - prototype walkthrough, then a **5-user usability test** before submission

## C3. Design principles
1. **Voice first, touch second, typing last.**
2. **One primary action per screen**, placed in the thumb zone.
3. **Safety is loud; everything else is calm.** Danger uses red + icon + words + haptic. Never colour alone. The rest of the UI stays quiet so alarms mean something.
4. **Show your work.** Every AI-drafted field shows the words it was heard from. Drafted and confirmed states look clearly different.
5. **Never lose work.** Autosave, offline by default, undo, drafts survive crashes and dead batteries.
6. **Honest status.** Sync state, offline state and "AI is drafting, about 1 min" are always visible and truthful.
7. **Speak their language, fully.** Localised, not just translated: culturally resonant imagery, local date/number formats, Yoruba microcopy reviewed by native speakers.
8. **Fast on the cheapest phone** (budgets in C6).
9. **Accessible by default:** WCAG 2.2 AA, touch targets ≥ 48 dp (56 dp for primary actions, glove-friendly), dynamic text size, screen-reader labels, reduced-motion support.

## C4. Visual identity (direction; to be validated in the prototype)
- **Concept: "Adire, digitised."** Adire is the Yoruba indigo resist-dyed textile.
  - **Deep indigo** is the primary colour, with warm cotton/shea neutrals and a terracotta accent.
  - Semantic colours are kept **distinct from the brand**: danger red, caution amber, confirmed green.
  - All pairs are contrast-checked by script, and a **Sunlight mode** targets 7:1 contrast.
- **Pattern:** subtle Adire motifs only on onboarding, empty and success states. **Never behind data.**
- **Type:** **Noto Sans** for full Yoruba diacritic support (dot-below + tone marks: *ẹ̀jẹ̀, ọ̀sẹ̀, ìrora*). Body text ≥ 17 px; tabular numerals for vitals; a 1.25 scale.
- **Layout:** 8-pt spacing grid, 12–16 px radii, near-flat elevation (battery- and sunlight-friendly).
- **Iconography:** a custom, rounded illustrative icon set for each danger sign (bleeding, severe headache, blurred vision, convulsions, fever, swelling, reduced fetal movement), so recognition doesn't depend on reading.
- **Motion:** 150–250 ms, purposeful (recording pulse, confirm-hold fill, sync tick). Respects reduced-motion.
- **Themes:** light, dark, Sunlight (high contrast).

## C5. Core flows and screens
1. **Today:** one large "Start visit" button; a "needs your review" queue; a sync pill (✓ synced / ⟳ 3 waiting / offline).
2. **Capture:**
   - a language chip (Yorùbá / English / auto)
   - a large live waveform with elapsed time, pause and stop
   - **danger-sign chips can be tapped at any moment**
3. **Instant safety panel:** tapping a danger sign shows, within 100 ms and offline:
   - a full-width red banner, *"Refer now: severe headache + BP ≥ 160/110"*
   - the National Standing Orders citation
   - a one-tap referral note
4. **Draft review:** grouped cards (Vitals, Pregnancy, Findings, Danger signs, Plan).
   - Each field shows its value and a **"heard: '…ẹ̀jẹ̀ ń jáde…'" evidence chip** that highlights the source words.
   - AI-drafted fields have a soft "draft" treatment until confirmed.
   - NEEDS_REVIEW fields are amber and say why.
   - Numeric keypad for vitals.
5. **Confirm:** **press-and-hold** to confirm (prevents accidental taps). A confirmed record is locked; changes are made as amendments.
6. **Referral note:** English for the receiving facility and a plain Yoruba explanation for the mother. Share via WhatsApp, SMS or print.
7. **Monthly report:** NHMIS ANC indicators counted automatically, compared with last month, sent to the in-charge for sign-off, then exported or pushed.
8. **Onboarding:** facility enrolment by HFR code, language, PIN, mic test. Under 2 minutes.

## C6. Performance budgets (enforced in CI)
- First load ≤ **200 KB** JS + CSS gzipped
- Font subset (Latin + Yoruba diacritics) ≤ 60 KB
- **Interactive ≤ 3 s on a low-end Android over 3G**; repeat loads instant from cache
- No layout shift
- No background polling; sync is event-driven

## C7. How we'll know it's good
- Usability test with 5 health workers. Tasks:
  - record a visit
  - correct a wrong BP
  - respond to a danger sign
  - sign off the monthly report
- Measures: task success, time on task **vs paper**, error rate, and the **System Usability Scale (SUS)**. Target ≥ 75, aiming for 80+.
- Accessibility: axe-core with zero critical issues, plus a manual screen-reader pass.

## C8. Design deliverables (in the repo)
- design tokens (JSON → CSS variables)
- component library with a story/preview page
- screen specs, accessibility checklist, usability report
- **a clickable prototype first**, for Malik and the nurse to review **before** screens are built
