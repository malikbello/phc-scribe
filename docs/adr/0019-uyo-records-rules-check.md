# ADR-0019: Check the danger-sign rules on real Uyo antenatal records

- **Status:** Accepted by Malik, 1 Oct 2026
- **Date:** 2026-10-01
- **Adds:** a reported supplement to `docs/eval-plan.md` §3. It does not change the counted benchmark (ADR-0016 / ADR-0018).

## Context
- The rules engine (`rules/danger_signs.v0.yaml`, 18 rules) decides which findings and vitals raise a referral flag (ADR-0003). So far it is tested only on golden tests and generated notes (G): **no real patient data has touched it.**
- Data survey round 6 found **real, openly licensed antenatal records**: St Luke's General Hospital, Anua, Uyo (Akwa Ibom), 2014–2019. OSF `j9zh8` (doi 10.17605/OSF.IO/J9ZH8), paper PMC12815018, **CC-BY-4.0** (GPS columns are restricted; we never use them).
- The "Martanal" sheet has **538 antenatal mothers**, each with: blood pressure (all 538 parse; 42 at ≥ 140/90, 14 at ≥ 160/110), temperature, weight, one symptom label (51 distinct, e.g. "Bleeding per vaginam" 12, "Swollen legs" 11, "Severe headache" 1, "Liquor drainage" 1, "Difficult breathing" 17) and one clinician diagnosis (29 distinct, e.g. Hypertension 28, Eclampsia 16, Pre Eclampsia 3, Proteinuria 19, Antepartum haemorrhage 3, Oedema 10).
- These are structured fields, not free text, so they **cannot** test the language model's extraction. They **can** test whether our rules flag real Nigerian antenatal patients the way their clinicians diagnosed them.

## Decision
1. **Stratum "U" (reported, not counted):** the 538 Uyo antenatal records, pinned by file SHA-256 at download.
2. **Mapping, written down before any result is looked at** (committed as `bench/uyo.py` with tests):
   - Vitals go straight into the record: BP (systolic/diastolic), temperature.
   - Symptom labels map to our findings by a fixed table (e.g. "Bleeding per vaginam" / "Bleeding" → `vaginal_bleeding` present; "Swollen legs" → `leg_oedema`; "Severe headache" → `severe_headache`; "Difficult breathing" / "Abnormal breathing" → `breathing_difficulty`; "Liquor drainage" → `leaking_amniotic_fluid`; "Protein in Urine" → urine protein positive). Labels with no ANC finding map to nothing. The nurse confirms the table in the review app before the first run.
3. **What is measured:** the rules engine runs on each mapped record. Against the clinician diagnosis as reference:
   - **Sensitivity** of any referral flag for the danger diagnoses (Eclampsia, Pre Eclampsia, Hypertension, Antepartum haemorrhage, Placenta Previa, Proteinuria), and per rule family (BP rules vs Hypertension/Eclampsia).
   - **Flag rate** on "Normal scan result" records (an over-referral check).
   - Exact 95% CIs (Clopper–Pearson); small cells are reported as counts.
4. **Honesty rules:** the diagnosis is one label per visit, recorded for care, not research; a record can be "Malaria" and still hypertensive. Disagreements are reported, not explained away. Results are labelled "real records, structured fields; tests the rules, not the language model".

## Consequences
- The safety net gets a real-data check at almost no cost (CPU, minutes), which judges asked for ("real data, not simulated").
- The table is small; most findings in our vocabulary do not appear. It complements, and does not replace, the counted speech benchmark.
- Attribution: "Maternal, Neonatal and Child Health Datasets for Spatiotemporal Data Analytics", OSF, CC-BY-4.0; cited in the benchmark report and dataset card.
