# ADR-0023: Takada, the health-worker app: its own repo, phone + clinic hub + cloud, a protocol-driven visit guide, container- and Kubernetes-ready from day one

- **Status:** Accepted by Malik, 1 Oct 2026 ("Go")
- **Date:** 2026-10-01
- **Amends:**
  - ADR-0014: the PWA moves to its own repo and gains a clinic hub.
  - Architecture §10: "no Kubernetes" becomes Kubernetes-*ready* (manifests checked in CI, not operated).
  - Architecture C1: the name is **Takada** (Hausa *takarda*, "paper"); a formal trademark and domain check is still due.

## Context
- **The gap.** phc-scribe has the model, the benchmark, the rules engine and the `/v1` API, but no app a health worker uses. The NAIC panel weighs the working build most, and the demo video needs one.
- **A nurse's request (via Malik, 1 Oct).** Health workers sometimes forget what to ask. She asked for:
  - reminders of the questions to ask;
  - a summary, on request, of what has been asked and answered;
  - follow-up prompts when an answer calls for them.
- **The workload varies by two orders of magnitude.**
  - In Cross River State, 196 PHC centres recorded about 37,600 antenatal visits in a year, under one a day per centre on average. Activity standards there are 15 minutes for a first visit and 5 for a follow-up. Nurses and midwives are at about 40% of need. (WISN study, *Hum Resour Health* 2022, PMC8796321.)
  - Upgraded centres in Niger State see over 150 antenatal women a day (Nigeria Health Watch).
  - One design must serve a one-nurse centre and a busy one.
- **Constraints:**
  - The phones are low-end Android devices.
  - Connectivity is intermittent.
  - An 8B model cannot run on a phone. It runs on a laptop CPU at about 1–2 minutes per visit (architecture §9; to be measured).
  - The budget is $0.

## Decision
1. **Separate repo `malikbello/takada-app`** (private until submission).
   - It has its own release cycle, CI and deploys.
   - It talks to phc-scribe **only through the published `/v1` contract** (`docs/openapi.v1.json`). The TypeScript client is generated from that file, and CI fails if they drift.
   - Danger-sign rules and the ANC vocabulary are vendored from phc-scribe as versioned, checksummed JSON (the same pattern as the review app's export), so the phone applies exactly the rules the benchmark tested.
2. **Three tiers, split by urgency, not by device:**

   | Work | Where | Why |
   |---|---|---|
   | Recording, record store, danger-sign alerts, visit-guide checklist and follow-up prompts, summary-so-far | **Phone**, offline, instant | Deterministic rules and text matching; must never wait on a network |
   | Speech → structured record (ASR + fine-tuned N-ATLaS) | **Cloud** when online; **clinic hub** when offline | Too heavy for a phone; not needed instantly (the nurse confirms after the visit) |
   | Master record, FHIR R4 façade, DHIS2 reports, backups | **Cloud** | One source of truth; integrations live here |

3. **The clinic hub is a queue, not a live server.**
   - A laptop (later a mini-PC) on the clinic Wi-Fi runs the phc-scribe API with the local model, plus Takada's hub service.
   - Phones submit jobs; the hub processes them in priority order (danger-related first).
   - Capacity is measured by a load test and published as visits per hour per hardware tier.
   - Busy centres add a second worker machine, and the queue distributes the work.
   - **The hub is never a single point of failure:** phones keep working without it, and jobs wait on the phone.
   - When online, jobs go straight to the cloud, which is faster.
4. **Sync:**
   - **Append-only, content-addressed events:** an amendment references the event it changes, so replicas cannot conflict or lose data.
   - Phone ↔ hub over local Wi-Fi; hub ↔ cloud and phone ↔ cloud over the internet. Every event has a globally unique id, so delivery is idempotent.
   - **Pairing by QR code** from the hub (device key + pinned hub certificate).
   - Data is encrypted at rest on the phone.
   - Role-based access; remote device revocation; an audit log on every change.
5. **Visit guide (the nurse's request), with clinical safety by construction:**
   - **The questions and follow-ups come from protocol, not from the model.** The source is the WHO ANC Digital Adaptation Kit contact schedule, plus the National Standing Orders. Each item cites its source, and Rahmat signs off the list in the review app.
   - The system only *detects* which items the conversation has covered (vocabulary and rules on the phone; the model's record when available).
   - It shows what is still unasked, and suggests follow-ups when a finding triggers them (e.g. headache → ask about blurred vision, check BP).
   - **Summary so far** is built from what has been detected, with the evidence quotes.
   - It never diagnoses or recommends treatment (architecture §10).
6. **Interoperability:**
   - A FHIR R4 Bundle export (Encounter, Observation, Condition, ServiceRequest, **Provenance**: "drafted by model X, confirmed by worker Y").
   - DHIS2 dataValueSets for the monthly NHMIS report.
   - For NAIC: export plus a push to the DHIS2 public test server.
   - Live integration with a hospital's EMR is a per-site project (SMART on FHIR / OAuth2) on the roadmap.
7. **Packaging and operations, mature from day one, at $0:**
   - Every service is a Docker image, built and scanned in CI.
   - `docker compose` sets up the clinic hub with one command.
   - **Kubernetes manifests** (Deployments, Services, probes, resource limits, HPA, NetworkPolicy) are linted and applied to a throwaway `kind` cluster in CI. They are not operated until a pilot needs them.
   - Liveness and readiness endpoints; structured logs with no clinical text; OpenTelemetry traces.
   - Uptime checks with alerting; SLOs from architecture B6.
   - Performance and accessibility budgets (ADR-0014): ≤ 200 KB JS + CSS, interactive ≤ 3 s on low-end Android over 3G, WCAG 2.2 AA with axe-core in CI.
   - Errors are surfaced, never swallowed: the client shows a recoverable error state and logs a coded error; no silent catch.

## Consequences
- **Gains:**
  - A demo that matches the real setting (phone + laptop, no internet), integration depth (N-ATLaS ASR + the fine-tuned model in the loop) and a feature health workers asked for.
  - The Track B story (who pays, how it scales) has a concrete hardware and sync answer.
- **Costs:** a second codebase in the last 10 days. Order of work, with cut lines in reverse:
  1. visit capture + danger alerts + record review/confirm (online);
  2. offline store + sync;
  3. visit guide;
  4. hub queue + pairing + Compose;
  5. FHIR / DHIS2 export;
  6. K8s manifests + kind check + uptime monitoring.
- **Risks:**
  - The visit-guide question list needs Rahmat's sign-off before the demo.
  - Hub throughput on the laptop CPU is unmeasured; the load test will say.
  - The name "Takada" needs a trademark and domain check before public launch.
