# Data audit: African Medical Records (Gate 1 input)

**Status: NOT RUN YET. Blocked on 29 Sept 2026:** the cloud dev environment's network policy refused `huggingface.co`, `hf.co` and `api.kaggle.com` (HTTP 403 from the egress proxy), so the dataset could not be read. The tooling is ready. Once the hosts are allowed, run the two commands below and fill in section 4 from the report. Nothing below section 3 is a finding yet.

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
_Pending the run._ Fill in from `data/audit/amr_audit.json`:
- revision audited:
- rows / splits / text or image:
- ANC notes (heuristic → after manual check):
- languages:
- identifiers found (rows by kind):
- license / consent / ethics statements:
- ANC notes with a danger keyword:
- **Gate 1 data decision:** ANC scope / enrichment gap / fallback / images-only (and why)

## 5. Known limits of the heuristics
- Visit type and language are keyword counts, good for sizing and not for labels. Every pilot and test item is read by a person.
- The identifier scan is a first pass (`serve/phc_scribe/deid.py`). It misses unlabelled names. Every test item gets a manual de-identification check.
- The danger-sign keyword list reuses the rung-1 baseline lexicon. It undercounts phrasings the lexicon does not know.
