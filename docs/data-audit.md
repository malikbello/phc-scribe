# Data audit: African Medical Records (Gate 1 input)

**Status: RUN on 29 Sept 2026** (revision `fa27d29`). Result: **the AMR dataset cannot supply the benchmark.** It has 62 records, and only 1–2 of them are antenatal. Section 3 was committed before the run (commit `4ba335c`) and was not edited afterwards. The data-source decision is Malik's (section 4).

## 1. How to run
```bash
pip install -e ".[data]"
python scripts/check_access.py   # HF identity, gated N-ATLaS listing, Kaggle auth; never prints tokens
python scripts/audit_amr.py      # streams the dataset; writes aggregates + private samples
```
Outputs:
- `data/audit/amr_audit.json`: aggregate counts only, pinned to the dataset revision (commit this)
- `data/private/amr_samples.jsonl`: 30 identifier-scrubbed notes for manual reading. Git-ignored; never commit, paste or print them.

## 2. Questions the audit must answer
| # | Question | Measured by |
|---|---|---|
| Q1 | How many notes, and are they text or only images? | rows per split; text vs image columns (`text_column_used`) |
| Q2 | How many are antenatal visits? | `visit_type_primary.anc` (keyword heuristic) + manual read of the 30 samples |
| Q3 | What language are they in? | `language_guess` + manual read |
| Q4 | Do they contain identifiers? | `rows_with_identifier` by kind (phone, name label, record number, date, address, 11-digit IDs) |
| Q5 | What do the license, consent and ethics statements say? | dataset card metadata + `topic_mentions`; then read the card in full |
| Q6 | Is there enough danger-sign content for ≥30% enrichment? | `anc_rows_with_danger_keyword` |
| Q7 | Do notes carry the fields we extract? | `rows_with_bp`, `rows_with_ga`; manual read |
| Q8 | Are there duplicates? | `exact_duplicates` (near-duplicates are checked at split time) |

## 3. Proposed Gate 1 decision rules (for Malik to approve before the audit runs)
Written down now so the audit result can't bend them.
- **ANC scope confirmed** if, after de-identification and dedupe, there are **≥ 300 usable ANC notes** (260 test + ≥ 40 for the pilot and dev split) **and** at least **80** of them (≈30% of the 260 test items) contain a danger sign.
- **Enrichment-only shortfall:** enough ANC notes but fewer than 80 with a danger sign. Keep ANC scope. Fill the gap only with **clinically reviewed rewrites of real notes**, labelled as such and reported separately. Constructed notes never count toward the 500 real items.
- **Fallback (ADR-0013):** fewer than 300 usable ANC notes means a general PHC encounter core plus the ANC danger-sign module. This needs a new ADR.
- **Images only (no usable text):** stop and decide between (a) manual transcription of ~300 notes by the team, (b) OCR plus manual correction, or (c) a different source. This changes the timeline, so Malik decides.
- **License or consent unclear:** evaluation-only use is acceptable if the license allows it. Training use waits for clarity. Everything is recorded in `docs/license-ledger.md`.

## 4. Results
Source: `data/audit/amr_audit.json`. Loader note: the repo ships a legacy loading script (`African-Medical-Records.py`), and current `datasets` releases refuse those. `scripts/audit_amr.py` therefore reads `metadata.csv` plus the `truth/*.txt` transcriptions directly. The images are counted, not downloaded.

- **Revision audited:** `fa27d29dae4128ac45f035fd580928c84bec4e98`
- **Q1 rows / splits / text or image:** **62 records**, one split. Each has handwritten PNG scans (74 pages: 57 records with 1 page, 4 with 3, 1 with 5) plus a ground-truth `.txt` transcription, so text is usable. Median 62 words (IQR 43–103, max 671). No empty texts, no exact duplicates. 15 contributors.
- **What the dataset is:** an **OCR/HTR benchmark**, not a record extract. The card lists "visit notes, prescriptions, nursing observation charts, lab request forms, clinical case scenarios" and says the records are **"synthesized/volunteer-produced clinical documents"**. So these are not real patient notes, even though they look like them.
- **Q2 ANC notes (heuristic):** primary visit type: general OPD 34, unknown 22, child 3, delivery/postnatal 2, **ANC 1**. Any ANC keyword: **2**. Only 1 row has a gestational-age pattern. A manual read of the 30 scrubbed samples is still to do, but it cannot change the order of magnitude.
- **Q3 languages:** English 62/62. No Yoruba, Hausa, Igbo or Pidgin detected.
- **Q4 identifiers (rows, first-pass scan):** any 46; date 42, labelled name 36, record number 16, phone 4, 11-digit ID 4. The records are synthesized, but they are formatted like real ones, so they still get the full de-identification pass.
- **Q5 license / consent / ethics:** CC-BY-4.0 (attribution required: "AMR Contributors", citation in the card). The card does not mention consent or ethics approval. It has one de-identification statement (the "synthesized/volunteer-produced" line). This is recorded in `docs/license-ledger.md`.
- **Q6 danger signs:** 18 rows hit a danger-sign keyword; **0** of them are ANC rows.
- **Q7 extractable fields:** BP pattern in 20 rows, gestational age in 1.
- **Q8 duplicates:** 0 exact.

### Gate 1 data decision (applying section 3 as written)
- **ANC scope: not met.** The rule needs ≥ 300 usable ANC notes with ≥ 80 danger-sign notes; AMR has ~1–2 and 0.
- **The ADR-0013 fallback does not rescue it either.** 62 records in total is far below the 500+ real items the benchmark needs, whatever the scope.
- **This is the "different source" case.** Section 3 lists it under images-only, but it applies equally here. **Malik decides.** Options, for the decision:
  a. **Find another real-note source**, e.g. a partner PHC/antenatal clinic via the UI/UCH ethics route (open item S2). This is the slowest option, and ethics approval before 12 Oct is unlikely.
  b. **Clinician-authored vignettes plus clinically reviewed rewrites.** The nurse and the student write ANC encounter notes from structured case templates in the style of real notes. This must be reported honestly as constructed data, which needs a change to the "constructed notes never count" rule, so it needs a new ADR.
  c. **A hybrid:** use AMR (62, CC-BY-4.0) as a small real-style *out-of-domain* robustness slice and as the OCR-input demo, and build the ANC benchmark as in (b).
  d. **Other public corpora** (Kaggle/HF search for Nigerian or African ANC or maternal notes). Worth a time-boxed search (≤ half a day) before choosing (b).
- The model half of Gate 1 (does base N-ATLaS show clear, fixable failures?) needs the 30 pilot items. It waits on this decision.

## 5. Known limits of the heuristics
- Visit type and language are keyword counts, good for sizing and not for labels. Every pilot and test item is read by a person.
- The identifier scan is a first pass (`serve/phc_scribe/deid.py`). It misses unlabelled names. Every test item gets a manual de-identification check.
- The danger-sign keyword list reuses the rung-1 baseline lexicon. It undercounts phrasings the lexicon does not know.
