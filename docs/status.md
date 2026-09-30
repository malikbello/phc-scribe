# Project status and working agreement

_Last updated: 30 Sept 2026, ~17:00 WAT (session 5). Keep this file current; it is the handoff between work sessions._

## Resume prompt (paste this into a new session)
> Read `docs/status.md` in phc-scribe (repo `malikbello/phc-scribe`, branch `main`; `day1-2-gate1` mirrors it) and follow its working agreement exactly: commits as `malikbello <139644523+malikbello@users.noreply.github.com>` with no AI attribution, no secrets in chat/code/logs, $0 unless I approve, ADRs for architecture changes, honest results. Then: (1) check the Kaggle notebook `bellomalik/phc-scribe-baseline` (read its log through the Kaggle API as described under "Kaggle" below; output files can't be downloaded from the cloud session), record the three baseline score reports in this file and commit; (2) push the 30-item pilot run; (3) continue with "Next steps, in order". Ask me before anything outward-facing or irreversible.

## Snapshot
- **What:** PHC Scribe. An offline-first AI scribe and safety net for Nigerian primary-health-care workers, built on a fine-tuned N-ATLaS.
- **Challenge:** NAIC 2026, **PS3 Sectoral Fine-Tuning: primary healthcare and community health**. Track B (Innovation & Enterprise), individual applicant with ID.
- **Deadline:** **12 Oct 2026, 23:59 WAT.** Target submission is **11 Oct** (one day of buffer).
- **Validation required:** a 500+ example benchmark vs base N-ATLaS on real data, plus a documented API.
- **Architecture:** approved 29 Sept (`docs/architecture.md`, ADRs in `docs/adr/`). **Evaluation:** `docs/eval-plan.md` (thresholds frozen after the pilot, before any training).

## Where things stand (30 Sept, end of session 4)
| Area | State |
|---|---|
| Benchmark design | **ADR-0016 accepted:** counted 500 = real NigBench-MAMAI speech (test split), labelled in the review app. Supplements: 300 generated notes (G), MamaBench, AMR. MAMAI access **still pending** (Intron emailed 29 Sept; follow up 2 Oct; fallback 5 Oct per ADR-0016 §6). |
| Baseline runs | **Done 30 Sept** (Kaggle run 08:04 UTC → finished between 16:01 and 16:11 UTC, all six runs complete). Results below and in `results/baseline-20260930/`. **Llama-3.1-8B few-shot beats N-ATLaS few-shot on every metric on G**; N-ATLaS few-shot is schema-invalid on 57/300. |
| Pilot | 30 dev items ready (`data/bench/pilot.20261004.jsonl`, stratum `pilot`). The Kaggle job is set to `PLAN = "pilot"` for its next push. After it: propose G1/G2 margins → Malik approves → freeze. **G2 needs a general-Yoruba regression set (not chosen yet).** |
| Fine-tuning | Pipeline built and CPU-smoke-tested; **nothing trained.** Order: pilot → freeze thresholds → `scripts/freeze_test_set.py` → generate training G with a **new** seed → `scripts/build_train_set.py` → `bench/train_qlora.py` on Kaggle. |
| API | `/v1` built (extract, check, records, transcribe with NCAIR1 ASR). Contract `docs/openapi.v1.json`, guide `docs/api.md`. 160 tests pass; CI green. |
| Cloud deploy | **ADR-0017 (Proposed): Modal**, private (proxy auth + API key) until submission, deployed from GitHub Actions. Modal: Starter, $30/month credits, **spend limit $0**. **First successful deploy: 30 Sept 15:21 UTC** (`deploy-modal` run #4, `main` @ `26906eb`) → `https://malikbello--phc-scribe-api-api.modal.run` (keyword extractor, HF ASR). Checked from the cloud session: `/v1/health` and `/v1/extract` without proxy auth return **401**. Still to check (Malik, needs the proxy token + API key): `/v1/health` returns 200 with both, and 401 with proxy auth but no key. Then accept ADR-0017. |
| Review app | Live at https://phc-scribe-review.vercel.app (Vercel project `phc-scribe-review`, Upstash Redis). Set "Calibration · MamaBench ANC": 20 items, **all** double-labelled. Admin can now delete an unlabelled set; share slider goes to 100%. Rahmat (clinician) and Oseni (annotator) **to be invited by Malik** in Admin → Team. |
| Data survey | WazobiaSpeech (`Africanvoice/*`): real consented health speech, CC-BY-4.0 for Pidgin/Igbo/Hausa, **Yoruba licence missing** (ask authors). Uses: ASR test, phrase mining, possible hard-negative stratum (needs an ADR). Kitala AI: paid service, not usable. |

## Baseline results (G, 300 generated English notes; 30 Sept)
Point estimate [95% group-bootstrap CI]. Prompt-v0.1, greedy, JSON-schema-constrained, `max_new_tokens = 768`. Reports: `results/baseline-20260930/`.

| Metric | N-ATLaS few-shot | Llama-3.1-8B few-shot | N-ATLaS zero-shot |
|---|---|---|---|
| Danger-sign recall | 0.735 [0.667, 0.800] | **0.876** [0.824, 0.924] | 0.565 [0.491, 0.643] |
| Micro-F1 | 0.466 [0.427, 0.506] | **0.813** [0.785, 0.842] | 0.318 [0.278, 0.358] |
| False-alarm rate (lower is better) | 0.187 [0.127, 0.250] | **0.020** [0.000, 0.045] | 0.100 [0.054, 0.151] |
| Item danger detection | 0.707 [0.634, 0.778] | **0.860** [0.803, 0.913] | 0.553 [0.475, 0.634] |
| Rule-flag recall | 0.741 [0.676, 0.805] | **0.903** [0.862, 0.942] | 0.444 [0.388, 0.502] |
| Schema-valid rate | 0.810 [0.763, 0.853] (243/300) | **0.990** [0.977, 1.000] | 0.920 [0.890, 0.950] |
| Ungrounded rate (lower is better) | 0.058 [0.047, 0.071] | **0.008** [0.003, 0.014] | 0.041 [0.019, 0.069] |
| BP exact | 0.810 | 0.990 | 0.283 |
| GA exact | 0.793 | 0.990 | 0.007 |

What this does and does not show:
- **G is generated and English-only**, so these are supplement results, not the counted benchmark (real MAMAI speech, ADR-0016), and there is **no Yoruba number yet**. Smoke (6 items, en + yo) is a pipeline check only.
- **N-ATLaS few-shot loses most on schema validity.** Its BP-exact rate equals its schema-valid rate (0.810), so every valid output had the right BP and every loss came from an invalid one. **Hypothesis (unverified):** outputs hit the 768-token cap and were cut mid-JSON (constrained decoding only guarantees a valid prefix). Checking needs the `error` field in `preds/natlas-fewshot.g.jsonl` (Kaggle Output tab), or a log print in the next job.
- Zero-shot N-ATLaS almost never gets GA right (0.007): without examples it does not use the expected format.
- **Decision for Malik before the freeze:** P1/P2 compare against *base N-ATLaS few-shot*. If the invalid outputs are truncation, raising `max_new_tokens` is a fairer baseline and must be decided **before** thresholds are frozen, not after. Llama-3.1 few-shot is a strong reference point that the fine-tuned model should be reported against too.

## Where everything lives
| Thing | Location |
|---|---|
| Code | GitHub `malikbello/phc-scribe` (private), branch `main` (production). Local clone in the cloud session: `/home/user/phc-scribe` |
| Kaggle notebook (baseline + pilot runs) | https://www.kaggle.com/code/bellomalik/phc-scribe-baseline (private). Output files: notebook → **Output** tab → `preds/*.jsonl` and `*.report.json` |
| Kaggle code bundle | private dataset https://www.kaggle.com/datasets/bellomalik/phc-scribe-code (built from `git archive HEAD` by `scripts/kaggle_push.py`; no private data) |
| Kaggle job source | `kaggle/baseline/run.py` (`PLAN` switch) + `kernel-metadata.json` (T4, internet on, private) |
| Reading the Kaggle log from a cloud session | Kaggle API `list_kernel_session_output` (helper written in session 4 at the scratchpad `klog.py`; recreate if gone: `KaggleApi().authenticate()`, `ApiListKernelSessionOutputRequest(user_name="bellomalik", kernel_slug=...)`, read `.log`). The log is only complete after the run ends. |
| Review app | https://phc-scribe-review.vercel.app; source `review-app/`; env vars `SESSION_SECRET`, `REVIEWERS` (Malik's admin code is in `REVIEWERS` in the Vercel dashboard) |
| Modal deploy | `deploy/modal_app.py` (set `PRIVATE = False` on submission day), workflow `.github/workflows/deploy-modal.yml` (manual: Actions → deploy-modal → Run workflow) |
| GitHub secrets (Actions) | `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `HF_WRITE_TOKEN` (spare; was for the HF Space), `HF_READ_TOKEN`, `PHC_API_KEY` (Malik keeps the key in his password manager; services only ever get its SHA-256 hash) |
| Decisions | `docs/adr/0001`–`0018` (0016 accepted 30 Sept; 0017 and 0018 proposed) |
| Benchmark data | `data/bench/g.20261002.jsonl` (300, test supplement G), `data/bench/pilot.20261004.jsonl` (30, dev), `tests/fixtures/smoke_items.jsonl` (6, constructed); private queues in `data/private/` (git-ignored) |

## Next steps, in order
1. ~~**Baseline results**~~ **(done 30 Sept; see Baseline results):** read the Kaggle log when the run ends; put the three reports (N-ATLaS few-shot, Llama-3.1 few-shot, N-ATLaS zero-shot on G) in this file. If the 12 h limit cut the last run, re-run only what is missing.
2. **Pilot:** `python scripts/kaggle_push.py` (the job is already `PLAN = "pilot"`), read the log, propose G1 (false-alarm margin) and G2 (general-Yoruba regression margin, after choosing a licensed general-Yoruba set) in `docs/eval-plan.md` §6 → Malik approves → commit the freeze.
3. **Freeze the test set** (`scripts/freeze_test_set.py data/bench/g.20261002.jsonl` plus S4 once MAMAI arrives; the script never overwrites an existing freeze, so decide the file list first).
4. **Training data and QLoRA run** on Kaggle (split long jobs so each stays well under 12 h).
5. **Modal:** ~~run `deploy-modal`~~ (done 30 Sept 15:21 UTC; unauthenticated requests refused), check `/v1/health` and that requests without proxy auth and without the API key are refused; Malik accepts ADR-0017.
6. **MAMAI:** when access arrives, `scripts/fetch_mamai.py` → upload the S4 queue in the review app → Malik labels (~9–10 h for 500).
7. Optional, CPU only: ASR word-error rate on ~100 WazobiaSpeech health clips (greedy vs beam search).
8. Submission package (last 2 days): README, benchmark report, model card, dataset card, demo video; set `PRIVATE = False` and redeploy; grep public docs for day/gate wording.

## Working agreement (non-negotiable)
1. **Malik Bello is the sole contributor.** Every commit is authored and committed as `malikbello <139644523+malikbello@users.noreply.github.com>`. **No co-author trailers, session links, or AI attribution** in commits, PRs, code, comments or docs.
2. **Secrets never appear** in chat, code, logs or commits. They are read only from environment variables.
3. **$0 cash budget.** No paid services unless Malik explicitly approves.
4. **Approval gates:** architecture changes go through a new ADR; build scope beyond the approved architecture needs Malik's OK.
5. **Honesty:** results are reported as measured, including failures against the pre-registered criteria.

## Environment (cloud dev sessions)
- Environment variables: `HF_TOKEN` (HF read token), `KAGGLE_API_TOKEN` (Kaggle `KGAT_…` token). The Kaggle CLI/API reads `KAGGLE_API_TOKEN` directly, so no token file needs to be written. Modal tokens are **GitHub secrets** only (see Where everything lives); this session cannot reach Modal.
- Network: `kaggleusercontent.com` (Kaggle output files) and `kitala.ai` are blocked; `api.modal.com` is unreachable (gRPC). Intended allowlist: `huggingface.co`, `*.huggingface.co`, `hf.co`, `*.hf.co`, `kaggle.com`, `*.kaggle.com`, `storage.googleapis.com` (+ `api.modal.com`, `modal.com`, `*.modal.run` if Modal is adopted).
- ✅ **29 Sept, session 3:** HF and Kaggle are reachable. `python scripts/check_access.py` passes: HF identity, the gated `NCAIR1/N-ATLaS` listing (12 files, 4 weight files, no GGUF), the AMR dataset and Kaggle auth.
- **Modal:** used only through GitHub Actions (`deploy-modal.yml`), because the cloud session cannot reach it.
- Local dev: `pip install -e ".[dev,data]"` (or `pip install --require-hashes -r requirements/ci.lock && pip install --no-deps -e .`), then `ruff check . && ruff format --check . && pyright && pytest`.
- N-ATLaS gated access: granted on all 5 NCAIR1 repos (N-ATLaS, Hausa/Yoruba/Igbo ASR, NigerianAccentedEnglish).
- Dev container: 4 CPU, ~15 GB RAM, ~30 GB free disk, no GPU.
- **Malik's laptop (offline node):** Dell Latitude 5400, i7-8665U, 16 GB RAM, no usable GPU, Windows 11 + WSL2, Ollama installed. **Disk must be freed to at least 25 GB.**
- **Cloud serving:** Modal, private behind proxy auth until submission (ADR-0017, Proposed). The free HF Space (ADR-0015) is closed: Docker Spaces now need PRO.

## Submission conventions (decided 29 Sept; apply from now)
Judges see the repo, the benchmark report, the API docs and the demo. They don't see our schedule.
- **Internal only:** `docs/status.md` (this file: day plans, progress log, open items). The internal "Gate N" labels live only here and in the ADRs.
- **Public docs use method language.** "Gate 1" becomes **"pre-registered decision point: data feasibility"** (and later "baseline adequacy", "fine-tune go/no-go"). Pre-registration is a strength, so we show it as methodology, not as a timeline.
- **No "day N" in filenames, branch names, headings or commit subjects.** Branches are named by feature (`data-audit`, `benchmark-v0`, `api-v1`) and merged into `main` promptly. `day1-2-gate1` is the last one named this way; merge it, then delete it.
- **Submission package** (built in the last 2 days): `README.md` (product + quickstart), `docs/benchmark-report.md` (pre-registered criteria vs measured results, including failures), `docs/api.md` + OpenAPI, a model card, a dataset/benchmark card with licence attributions, and the demo link. The final pass greps for `day[ -]?[0-9]` and `Gate [0-9]` in the public files.

## Team
- Malik Bello: lead, ML/engineering, native Yoruba reviewer
- Rahmat Adebayo, registered nurse, UCH Ibadan: clinical adviser/adjudicator (**to confirm as a named member**)
- Oseni Abdullah, medical student: annotator (**to confirm as a named member**)

## Open items (Malik unless noted)
| Item | Status |
|---|---|
| Invite Rahmat (Clinician) and Oseni (Annotator) in the review app; label the calibration set | Pending |
| Confirm Rahmat and Oseni as named team members (Track B needs 2–5) | Pending |
| Follow up with Intron on NigBench-MAMAI access (2 Oct); fallback 5 Oct | Pending |
| Accept or reject ADR-0018 (WazobiaSpeech as the real-data fallback, replacing MamaBench + G) | Pending |
| Accept ADR-0017 (Modal) after the first successful deploy | Pending |
| Ask the WazobiaSpeech authors (EqualyzAI / DSN) about the Yoruba licence | Pending |
| Agent name: Àkọsílẹ̀ / Olùgbọ́ / Magatakarda (Akọ̀wé and Ìtọ́jú are taken) | Pending |
| Email organisers about the team-size mismatch (track cards say 2–5, FAQ says 1–6) | Pending |
| Free ≥25 GB of laptop disk (offline node, demo video) | Pending |
| Nurse review of annotation guidelines, vocabulary and rules (now done in the review app's sign-off) | Pending |
| Review/extend the draft Yoruba forms in `bench/baselines/lexicon.v0.yaml` | Pending |
| Remove day/gate wording from public docs before submission (Claude) | From now |
| Optional: delete the unused `HF_WRITE_TOKEN` on Hugging Face and GitHub | Optional |

## Progress log
**30 Sept, session 5:**
- **Modal deployed** (run #4, 15:21 UTC) after the `MODAL_TOKEN_SECRET` fix; unauthenticated `/v1/health` and `/v1/extract` return 401.
- Tokens restored mid-session. **Baselines finished** (all six runs); reports recorded above and committed to `results/baseline-20260930/`.
- Session-start identity guard added (`.claude/settings.json`, `.githooks/commit-msg`).

**30 Sept, session 4 (later):**
- **Review app:** Rahmat/Oseni are invited by Malik in Admin → Team (bootstrap entries in Vercel were tried and removed). New admin *Delete set* (only before the first label) and a 0–100% double-label slider. Calibration set re-uploaded with every item double-labelled.
- **ADR-0016 accepted.** 30-item pilot set generated (`pilot.20261004`); G regenerates byte-identically.
- **Data survey round 4:** WazobiaSpeech and Kitala AI (`docs/data-sources-survey.md`, ledger row).
- **CI:** the secret scan flagged a literal test key in `tests/test_api.py`; test keys are now generated at runtime.
- **Cloud:** HF Docker Spaces now need PRO, so ADR-0015 is closed. ADR-0017 proposes Modal (deploy from GitHub Actions, private behind proxy auth, spend limit $0). The deploy workflow masks the key hash and strips whitespace from pasted tokens; one early failed run printed the key's SHA-256 hash (not the key) and its log was deleted.

**30 Sept, session 4, base-model runner:**
- `bench/prompts.py` (prompt-v0.1: one system prompt with the vocabulary, few-shot from 2 constructed smoke items) and `bench/runners/llm.py` (transformers + xgrammar JSON-schema-constrained greedy decoding; schema violations are scored, not crashes). Works on transformers 4.x and 5.x.
- Kaggle GPU job `kaggle/baseline/` (private notebook `bellomalik/phc-scribe-baseline`, T4). `scripts/kaggle_push.py` publishes the code as a private dataset `bellomalik/phc-scribe-code` from `git archive HEAD` (no private data) and pushes the notebook. Runs, in priority order: N-ATLaS few-shot, Llama-3.1-8B-Instruct few-shot, N-ATLaS zero-shot, on the smoke items and G.
- Comparator corrected to **Llama-3.1-8B-Instruct** (N-ATLaS's actual parent), from the ungated mirror `unsloth/Llama-3.1-8B-Instruct`; ledger row added.
- Cloud sessions cannot download Kaggle output files (`kaggleusercontent.com` is outside the proxy allowlist), but the run log is readable through the API, and the job prints each score report into it.
- First GPU run (v2) failed on every item: transformers 5 returns a dict from `apply_chat_template`. Fixed; v3 running.
- **Fine-tune pipeline ready (no training yet):** `scripts/freeze_test_set.py` (hashes the test files into `data/bench/test-manifest.json`; never overwrites a freeze), `scripts/build_train_set.py` (refuses to run before the freeze or if a frozen file changed; drops items sharing a group with, duplicating or near-duplicating a test item), `bench/train_qlora.py` + `configs/qlora.v0.yaml` (QLoRA r=16 on attention + MLP, assistant-only loss, saves adapter + config + metrics), and `--adapter` / `--mode finetuned` in the runner. Smoke-tested end to end on CPU with a 135M model. Fine-tuned prompt: about 130–170 tokens vs about 2,500 few-shot.
- **Order of operations (eval plan):** 30-item pilot → freeze thresholds → freeze test set → generate training data with a new seed → train. Nothing is trained before both freezes.
- **`/v1` API** (`serve/phc_scribe/api/`, FastAPI): extract, check, versioned records (append-only SQLite, idempotency keys, confirm/amend), hashed API keys, per-key rate limit, error envelope, request ids, no clinical text in logs. Model-agnostic: keyword baseline or the fine-tuned GGUF via llama.cpp. Contract `docs/openapi.v1.json` (CI drift check), guide `docs/api.md`. `/v1/transcribe` added (NCAIR1 ASR per language; verified on real WazobiaSpeech Pidgin clips, about 8 s for a 6 s clip on 4 CPU cores). The HF Space route is closed (Docker Spaces now need PRO); see ADR-0017.

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

**29 Sept, session 3 (round 5):**
- Stratum G generated (300 notes, verified).
- Nurse kit built: a clinical review pack, generated from the repo by `scripts/build_review_pack.py`, covering the vocabulary, the 18 rules, the phrase bank and the §9 questions.
- A 20-item MamaBench calibration queue (no hints) for Malik and the nurse to label independently, as a first agreement check.
- Quickstart for labellers: `docs/labelling-quickstart.md`.

**29 Sept, session 3 (round 6), review app:** `review-app/` is a Next.js app on Vercel with Upstash Redis.
- **What reviewers do:** tap-first clinical sign-off and labelling, 20% of items double-labelled for kappa, admin exports that feed `build_s4_items.py` (verified end to end).
- **Team:** invite and revoke reviewers from the admin screen with no redeploy; codes are stored only as HMAC hashes.
- **Operations:** a health endpoint and batched Redis reads for scale; CI job `review-app`; `main` is production.
- **Data:** med-convo-nig access granted; NigBench-MAMAI and nig-bench still pending.

