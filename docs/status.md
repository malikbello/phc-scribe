# Project status and working agreement

_Last updated: 29 Sept 2026. Keep this file current; it is the handoff between work sessions._

## Snapshot
- **What:** PHC Scribe. An offline-first AI scribe and safety net for Nigerian primary-health-care workers, built on a fine-tuned N-ATLaS.
- **Challenge:** NAIC 2026, **PS3 Sectoral Fine-Tuning: primary healthcare and community health**. Track B (Innovation & Enterprise), individual applicant with ID.
- **Deadline:** **12 Oct 2026, 23:59 WAT.** Target submission is **11 Oct** (one day of buffer).
- **Validation required:** a 500+ example benchmark vs base N-ATLaS, plus a documented API.
- **Architecture:** approved 29 Sept. See `docs/architecture.md` and the decision records in `docs/adr/`.
- **Evaluation:** `docs/eval-plan.md`. Thresholds are frozen after the 30-item pilot, **before any training**.

## Working agreement (non-negotiable)
1. **Malik Bello is the sole contributor.** Every commit is authored and committed as `malikbello <139644523+malikbello@users.noreply.github.com>`. **No co-author trailers, session links, or AI attribution** in commits, PRs, code, comments or docs.
2. **Secrets never appear** in chat, code, logs or commits. They are read only from environment variables.
3. **$0 cash budget.** No paid services unless Malik explicitly approves.
4. **Approval gates:** architecture changes go through a new ADR; build scope beyond the approved architecture needs Malik's OK.
5. **Honesty:** results are reported as measured, including failures against the pre-registered criteria.

## Environment (cloud dev sessions)
- Environment variables: `HF_TOKEN` (HF read token), `KAGGLE_API_TOKEN` (Kaggle `KGAT_…` token). The Kaggle CLI/API reads `KAGGLE_API_TOKEN` directly, so no token file needs to be written. For Modal: `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` (not added yet).
- Intended network allowlist: `huggingface.co`, `*.huggingface.co`, `hf.co`, `*.hf.co`, `kaggle.com`, `*.kaggle.com`, `storage.googleapis.com` (+ `api.modal.com`, `modal.com`, `*.modal.run` if Modal is adopted).
- ✅ **29 Sept, session 3:** HF and Kaggle are reachable. `python scripts/check_access.py` passes: HF identity, the gated `NCAIR1/N-ATLaS` listing (12 files, 4 weight files, no GGUF), the AMR dataset and Kaggle auth.
- **Modal:** tokens **verified on the laptop** on 29 Sept (`modal app list` works; no apps yet; profile `malikbello`). The cloud dev sessions cannot reach Modal, because its client uses gRPC, which the egress proxy blocks. So Modal jobs are launched from the laptop, or from a Kaggle notebook. Adopting Modal still needs an ADR superseding ADR-0015, plus a spend limit.
- Local dev: `pip install -e ".[dev,data]"` (or `pip install --require-hashes -r requirements/ci.lock && pip install --no-deps -e .`), then `ruff check . && ruff format --check . && pyright && pytest`.
- N-ATLaS gated access: granted on all 5 NCAIR1 repos (N-ATLaS, Hausa/Yoruba/Igbo ASR, NigerianAccentedEnglish).
- Dev container: 4 CPU, ~15 GB RAM, ~30 GB free disk, no GPU.
- **Malik's laptop (offline node):** Dell Latitude 5400, i7-8665U, 16 GB RAM, no usable GPU, Windows 11 + WSL2, Ollama installed. **Disk must be freed to at least 25 GB.**
- **Cloud serving:** Modal was dropped because the virtual card was rejected (ADR-0015). The fallback is a free Hugging Face Space (CPU). **29 Sept: Malik now has a Modal account.** Using it needs a new ADR superseding ADR-0015 and a spend limit so usage stays within free credits ($0 rule). Tokens: create in the Modal dashboard (Settings → API Tokens) and add as environment variables; never paste them in chat. Laptop CLI note: `modal token new` fails on the laptop's Windows Python 3.9 (a `typing` bug hit by recent `aiohttp`). Use WSL2 or Python ≥ 3.11.

## Submission conventions (decided 29 Sept; apply from now)
Judges see the repo, the benchmark report, the API docs and the demo. They don't see our schedule.
- **Internal only:** `docs/status.md` (this file: day plans, progress log, open items). The internal "Gate N" labels live only here and in the ADRs.
- **Public docs use method language.** "Gate 1" becomes **"pre-registered decision point: data feasibility"** (and later "baseline adequacy", "fine-tune go/no-go"). Pre-registration is a strength, so we show it as methodology, not as a timeline.
- **No "day N" in filenames, branch names, headings or commit subjects.** Branches are named by feature (`data-audit`, `benchmark-v0`, `api-v1`) and merged into `main` promptly. `day1-2-gate1` is the last one named this way; merge it, then delete it.
- **Submission package** (built in the last 2 days): `README.md` (product + quickstart), `docs/benchmark-report.md` (pre-registered criteria vs measured results, including failures), `docs/api.md` + OpenAPI, a model card, a dataset/benchmark card with licence attributions, and the demo link. The final pass greps for `day[ -]?[0-9]` and `Gate [0-9]` in the public files.

## Team
- Malik Bello: lead, ML/engineering, native Yoruba reviewer
- Registered nurse, UCH Ibadan: clinical adviser/adjudicator (**to confirm as a named member**)
- Medical student: annotator (**to confirm as a named member**)

## Open items
| Item | Owner | Status |
|---|---|---|
| Agent name: Àkọsílẹ̀ / Olùgbọ́ / Magatakarda (Akọ̀wé and Ìtọ́jú are taken) | Malik | Pending |
| Confirm the nurse and the student as team members | Malik | Pending |
| Email organisers about the team-size mismatch (track cards say 2–5, FAQ says 1–6) | Malik | Pending |
| Free ≥25 GB of laptop disk | Malik | Pending |
| Revoke the HF/Kaggle tokens pasted in chat on 29 Sept; create new ones in the environment | Malik | Reported done; confirm the old ones are revoked |
| UI/UCH ethics route for real Yoruba dictations (S2, acceleration phase) | Nurse | Not started |
| Faster cloud serving (card / Lightning / ZeroGPU) | Malik | Modal account now available; ADR + spend limit + tokens in environment pending |
| **Gate 1 data-source decision:** AMR has 62 records and ~1 ANC note (`docs/data-audit.md` §4, options a–d) | Malik | **Blocking Gate 1** |
| HF access: MamaBench ✅ granted. NigBench-MAMAI, nig-bench, med-convo-nig still show **"awaiting review"** for account `malikbello`. Confirm the approval was for this account | Malik | Pending |
| **Accept or reject ADR-0016** (revised: counted 500 = real NigBench-MAMAI speech, labelled by Malik; generated notes as a supplement) | Malik | **Blocking the benchmark build** |
| **Email Intron Health (tobi@intron.io)** to ask for approval of the pending access requests; fallback in ADR-0016 §6 (2 Oct / 5 Oct) | Malik | **Today** |
| Nurse: about 1 h (double-label 50 items) + 1.5 h (rules/vocabulary review) + optional demo test. Confirm her and the student as named team members (Track B needs 2–5) | Malik | Pending |
| Before submission: remove day/gate wording from public docs (see Submission conventions) | Malik + Claude | From now |
| Gate 1 decision rules (`docs/data-audit.md` §3): committed before the audit ran and applied as written. Confirm | Malik | Pending |
| Review annotation guidelines v0, finding vocabulary, danger-sign rules v0 (open questions in guidelines §9) | Nurse | Pending |
| Review/extend the draft Yoruba forms in `bench/baselines/lexicon.v0.yaml` | Malik | Pending |
| Merge branch `day1-2-gate1` into `main` | Malik | Pending |

## Progress log
**29 Sept, session 2** (branch `day1-2-gate1`; not merged yet). What changed:
- **Access check** `scripts/check_access.py`: HF identity, gated N-ATLaS listing, dataset reachability, Kaggle auth. Output passes through a mask for any secret-like env value. Ran it: both tokens are set; HF and Kaggle are **blocked by the network policy**.
- **Data audit tooling** `scripts/audit_amr.py` + `bench/data_audit.py`: streams the dataset, pins its revision, and writes aggregate counts only to `data/audit/amr_audit.json`. Scrubbed samples go to the git-ignored `data/private/`. **Not run yet (blocked).** The protocol and proposed decision rules are in `docs/data-audit.md`.
- **Schema v0.1:** Pydantic models (`serve/phc_scribe/encounter.py`) are the source of truth. `schema/encounter.v0.1.json` is generated from them (CI checks drift). Findings carry assertion status (present/absent/possible/historical/not_mentioned) and a verbatim evidence quote. Units are UCUM. Vocabulary: `schema/vocab/anc_concepts.v0.1.yaml`, 14 danger signs + 15 other ANC symptoms, with **unverified** WHO ANC DAK mappings.
- **Annotation guidelines v0** `docs/annotation-guidelines.md` (open questions for the nurse in §9). **License ledger** `docs/license-ledger.md`.
- **Grounding + value checks** `serve/phc_scribe/grounding.py`: exact, then diacritic-folded quote matching with offsets mapped back to the original text. Also physiological ranges and a digits-in-quote check. Failures are dropped and the record is marked NEEDS_REVIEW.
- **Rules engine** `serve/phc_scribe/rules.py` + `rules/danger_signs.v0.yaml`:
  - 18 rules (14 finding rules; severe/any hypertension; pre-eclampsia combination; severe anaemia)
  - declarative conditions, validated at load
  - golden tests per rule
  - every source reference is marked `verified: false` until checked
- **Baseline ladder, rung 1** `bench/baselines/keyword.py`: keywords plus NegEx-style cues, and regexes for note shorthand (BP, 32/40, G3P2, PCV, TCA 2/52). The Yoruba forms are drafts.
- **Bench harness:**
  - `bench/metrics.py`: danger-sign recall, micro-F1, false-alarm rate, exact match, schema-valid rate, ungrounded rate, rule-flag recall
  - `bench/stats.py`: group-resampled bootstrap CIs, paired bootstrap difference, exact McNemar
  - `bench/harness.py`: CLI to run systems and score them
- **De-identification v0** `serve/phc_scribe/deid.py`, covering Nigerian phone numbers, record numbers, labelled names, dates, addresses and 11-digit IDs.
- **CI** `.github/workflows/ci.yml`:
  - ruff, pyright, a schema drift check, pytest (131 tests, including a smoke-eval on 6 **constructed** items)
  - gitleaks secret scan
  - pip-audit
  - dependencies pinned with hashes in `requirements/ci.lock`

  Verified locally on Python 3.12, not yet on GitHub.

**29 Sept, session 3 (cont.)**: Modal verified from the laptop. **Data-source survey:** `docs/data-sources-survey.md`. No public corpus of real Nigerian ANC notes exists. The best anchors are Intron Health's Nigerian sets, above all **NigBench-MAMAI** (real Yoruba/Pidgin maternal-health speech, CC-BY-4.0, gated). Proposed benchmark: clinician-constructed ANC notes anchored in real phrasing, plus real-language, conversation and AMR slices. This needs an ADR.

**29 Sept, session 3** (branch `day1-2-gate1`):
- The access check passes (HF, gated N-ATLaS, dataset, Kaggle). Modal cannot be reached from the cloud session (gRPC); see Environment.
- **The data audit ran.** `scripts/audit_amr.py` now falls back to reading `metadata.csv` plus the `truth/*.txt` files, because current `datasets` refuses the repo's legacy loading script. The aggregates are in `data/audit/amr_audit.json`. 30 scrubbed samples are in the git-ignored `data/private/`; nobody has read them yet.
- **Finding:** AMR is a 62-record OCR/HTR benchmark of *synthesized/volunteer-produced* documents. They are English only and mostly general OPD; 1–2 are ANC and 0 ANC notes have danger signs. Under the §3 rules, **ANC scope fails, and the ADR-0013 fallback fails too** (62 ≪ 500). A new data source is needed. The options are in `docs/data-audit.md` §4. Pilot items and the model baselines wait on this decision.

**29 Sept, session 3 (round 3):** IyàwóBench checked: CC BY 4.0, but febrile triage only (0 ANC visits). MamaBench is accessible: 78 ANC vignettes, 37 with danger signs, CC-BY-4.0. The Intron gated sets are still pending. **ADR-0016 proposed:** author the ANC benchmark ourselves (licence-clean, releasable), with MAMAI as the real-language stratum and real clinical data as upside only.

**29 Sept, session 3 (round 4):** read the NAIC build requirements (`docs/naic-requirements.md`): validation must use real data, "not simulated". ADR-0016 revised: the counted benchmark is real NigBench-MAMAI speech. Built the S4 pipeline: `scripts/fetch_mamai.py` (text columns only, seeded stratified queue with keyword hints), an offline labeler at `tools/labeler/labeler.html` (browser-tested, works on a phone), and `scripts/build_s4_items.py` (evidence verified verbatim).

## Next steps: days 1–2 (Gate 1)
1. ✅ Access verified (HF, Kaggle). Modal: verify from the laptop.
2. ✅ Audit run; results are in `docs/data-audit.md` §4. ⛔ **Malik: choose the data source (options a–d)**, then read the 30 scrubbed samples. Option (b) or (c) needs an ADR that changes the "constructed notes never count" rule.
3. ✅ Drafted: schema v0.1, vocabulary, annotation guidelines v0, danger-sign rules v0. All need nurse review before gold labelling.
4. Pick 30 pilot items (after the audit). Rung 1 (keyword baseline) runs anywhere now via `python -m bench.harness`. Still to build: the model runner for rungs 2–4 (Llama-3-8B-Instruct, base N-ATLaS zero-/few-shot) with schema-constrained decoding on a Kaggle GPU (or Modal, if an ADR approves it). Also measure Q4 GGUF latency on CPU.
5. **Gate 1 decision:** does base N-ATLaS show clear, fixable failures, and does the data support ANC scope (or the general-PHC fallback, ADR-0013)?
6. In parallel: ✅ repo skeleton + CI. Still to do: API contract (`/v1` OpenAPI) and the design-tokens + clickable-prototype draft (after the name is picked).
