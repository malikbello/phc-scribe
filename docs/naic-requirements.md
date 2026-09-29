# NAIC 2026: requirements that bind us

_Source: https://ncair.nitda.gov.ng/naic/ (copied by Malik from the site on 29 Sept 2026). This lists only what binds PHC Scribe, quoted verbatim where it matters. Anything not listed here is our own choice (see `docs/adr/`), not a rule of the challenge._

## Problem statement and track
- **PS3 Sectoral Fine-Tuning.** "Develop specialised versions that understand the terminology and contexts of sectors…" Health is a named sector.
- **Track B, Innovation & Enterprise.** "Team Size **2–5 members**." "Individual applicants must be Nigerian citizens aged 18 or above." At least 50% of the team must be based in Nigeria. We submit a valid ID (no CAC certificate needed for individuals).
- All members must be Nigerian citizens. The work must be original and not previously awarded. One problem statement per team.

## Build requirements ("build, don't just propose")
1. **A working technical build:** software, deployed system, dataset, model or other functioning artefact.
2. **Genuine N-ATLaS integration:** "must use the N-ATLaS model, API, ASR service or training pipeline". Wrapping another general-purpose model does not qualify.
3. **Real-world validation:** "Evidence of testing with actual users, real data or live benchmarks. **Not simulated or hypothetical results.**"
   - **PS3 specifically:** "**Benchmark of 500+ examples vs base N-ATLaS**."

## Seven submission components
1. Working artefact (repo, deployed app, published model, live API or dataset)
2. N-ATLaS integration evidence
3. Real-world validation evidence
4. Technical documentation (architecture, setup, usage)
5. Video demonstration, **3–5 minutes**, end to end
6. Team profile (names, affiliations, roles of **all** members)
7. Endorsement/registration (Track B: ID)

## How it is judged
Multidisciplinary panel (AI experts, **sector specialists**, ONDI, NCAIR). "Focuses heavily on the quality of the working build and the depth of its integration with N-ATLaS."
1. Working artefact and technical rigour
2. N-ATLaS integration
3. Real-world validation
4. Impact potential
5. Scalability and sustainability
6. Team capability

## Dates
- Submission deadline: **12 Oct 2026, 23:59 WAT** (no late entries)
- N-ATLaS integration check: 15–17 Oct
- Shortlist: 16–20 Oct
- Acceleration: 25 Oct – 4 Nov
- Finals: 8–10 Nov

## What this means for us
- The counted 500+ benchmark items should be **real data**. Generated items may be reported, but only as a separately labelled supplement (ADR-0016).
- Using **N-ATLaS ASR as well as the LLM** (real voice → record) deepens integration, criterion 2.
- The team must be **at least 2 named members**; the nurse and the student need to be confirmed.
- **Evidence from real users** (health workers trying the demo, feedback documented) is a second kind of validation.
