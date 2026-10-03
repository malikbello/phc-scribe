# Project status and working agreement

_Last updated: 3 Oct 2026, afternoon WAT (session 6). Keep this file current; it is the handoff between work sessions._

## Resume prompt (paste this into a new session)
> Read `docs/status.md` in phc-scribe (repo `malikbello/phc-scribe`, branch `main`) and follow its working agreement exactly: commits as `malikbello <139644523+malikbello@users.noreply.github.com>` with no AI attribution (the `.githooks/commit-msg` guard rejects "claude", co-author or session lines), no secrets in chat/code/logs, $0 unless I approve, ADRs for architecture changes, honest results. Run `./scripts/ci_local.sh` before every push. Start from "Right now" and "Next steps, in order". Keep only truly human tasks human (labelling, clinical decisions, my approvals); automate the rest robustly. Ask me before anything outward-facing or irreversible (the freeze included). Update this file and the resume prompt at the end of every work block.

## Plan to win (agreed 3 Oct, session 6). Submission target 11 Oct; deadline 12 Oct 23:59 WAT
Malik: "innovate… let us win the hackathon with bright and shining colours"; "the best way without having to rely on people". Labellers: Malik, Rahmat, Success.

**What wins, mapped to the judging criteria (`docs/naic-requirements.md`):**
1. **Working artefact and rigour:**
   - Takada (phone, hub, cloud) running the fine-tuned Q4 N-ATLaS offline on the laptop;
   - a pre-registered benchmark with frozen tests;
   - committee labels with stratified PPI (ADR-0025).
2. **N-ATLaS integration:** both N-ATLaS models are fine-tuned: the LLM (ADR-0024) and the ASR (ADR-0026, proposed); N-ATLaS ASR feeds the LLM end to end.
3. **Real-world validation:**
   - 600 real speech clips;
   - 538 real Uyo records for the rules;
   - a short real-user pilot with the nurses (usability and time per record, 9 Oct).
4. **Impact:** maternal danger signs caught offline, in Yoruba and Pidgin, on cheap phones.
5. **Scalability:** hub and cloud architecture, Kubernetes, language packs.
6. **Team:** named nurses, a doctor, a pharmacist; clinical sign-off with a traceability matrix.

**Timeline:**
| Day | Work |
|---|---|
| 3 Oct (Sat) | Run A finishes → push `checks` (repetition penalty, ASR language) → build the committee labelling job (ADR-0025) → apply the nurses' sign-off (traceability matrix) → G1 decision → build the ASR fine-tune (if ADR-0026 is approved) |
| 4 Oct | `checks` results → committee run (3 models × 600) → strata, seeded sample uploaded to the review app → Malik, Rahmat and Success label about 70 each over 4–7 Oct → ASR fine-tune run |
| 5 Oct | Stage-1 freeze (Malik's "yes") → training set → runs B and C |
| 6 Oct | Dev evaluation → stage 2 (DPO) if needed |
| 7 Oct | Scale, merge, GGUF + imatrix, laptop latency → ASR evaluation |
| 8 Oct | Labels settled → stage-2 freeze → final scoring (base vs fine-tuned Q4, all strata, Belebele G2, audio condition) |
| 9 Oct | Real-user pilot with the nurses on Takada + hub → demo recording |
| 10 Oct | Benchmark report, model and dataset cards, technical docs, video edit |
| 11 Oct | Clean submission repo, submit |

GPU budget for the week: about 25 of 30 Kaggle hours (the quota resets weekly).

**Nurses' clinical sign-off (exported 3 Oct to `data/private/review/clinical-review.20261003.json`):**
- Rahmat and Success: 131/131 each; both "ok" on 89 items; 42 need a decision.
- **G1 (false alarms):** both reject the +5-point tolerance. Success: "unnecessary referrals should be avoided totally". Rahmat: "every alarm should be verified before referral". **Proposed: tighten G1 to +2 points** (Malik decides before the freeze). The product already makes the nurse confirm every flag.
- **BP:** "14/9 doesn't mean 140/90". Shorthand or incomplete BP is never acted on and is flagged for recheck (both nurses, Q3/Q4).
- **Uyo mapping:** both answered with specific mappings, so the ADR-0019 check can now run with `--confirmed-by`.
- **Phrases, guide and rules:** 31 change requests, mostly local and lay phrasings (e.g. "running temperature", "serious stomach pain", "spotting", "pale +++", ">3 vomits a day") and follow-up tests (urinalysis every visit; PCV with bleeding). To be applied via a traceability matrix (each note → applied, or declined with a reason).

## Right now (handoff, 3 Oct ~20:00 WAT, session 7)
**Malik's decisions, 3 Oct:** ADR-0026 (ASR fine-tune) **accepted**; G1 tightened to **+2 points** (eval plan §6), as both nurses asked; reviews he holds are open issues (#8 phrase bank, #9 teacher check, #10 start the Kaggle run); he will say when he wants to do them, and Claude guides.

**Kaggle:**
- `phc-scribe-baseline` v16 (`checks`, pushed through the API) stopped at once: no HF_TOKEN. Superseded.
- **`phc-scribe-committee` (ADR-0025), no secrets, started through the API:**
  - smoke run (16 items × 4 models): Qwen3-14B 16/16 valid, Phi-4 16/16; Gemma-3-12B and Mistral-Small-24B ran out of memory at batch 8; all were slow (30–50 s/item) because the 4-bit checkpoints compute in bfloat16, which the T4 emulates;
  - fixed: float16 compute on GPUs without bfloat16 (`bench/runners/llm.py`); **Phi-4 replaces Gemma-3-12B** (Gemma 3 overflows in float16; ADR-0025 amendment); Mistral at batch 4; predictions written every 64 items; an 11-hour budget split across members;
  - **full run (v3, 3 models × 600) running.** When done: `python scripts/kaggle_log.py --slug phc-scribe-committee --save results/committee`, then `python -m bench.committee triage --queue data/private/label_queue.s4w.jsonl --pred data/private/kaggle/committee.qwen3-14b.jsonl --pred data/private/kaggle/committee.phi-4-14b.jsonl --pred data/private/kaggle/committee.mistral-small-24b.jsonl --out-dir data/private/committee`, then upload `label_queue.committee-sample.jsonl` (about 180 clips) to the review app as a new set.
- **ADR-0026 built:** `bench/asr_finetune.py` (recipe in its docstring; CPU smoke test passed with whisper-tiny), `bench/asr_run.py --models/--split`, `scripts/asr_compare.py` (paired speaker bootstrap; reproduces Run A exactly; base CER 28.8% pcm, 26.1% yo). **`phc-scribe-baseline` plan `checks_asrft`**: the checks, then Yoruba on GPU 0 and Pidgin on GPU 1 in parallel, then the test pool with base-forced and fine-tuned-forced models. **Malik starts it from the editor (HF_TOKEN), issue #10.** Then: `kaggle_log.py --save results/asrft`, `python scripts/asr_compare.py --base data/private/kaggle/asr-base-forced.jsonl --candidate data/private/kaggle/asr-ft-forced.jsonl --out results/asr/ft-vs-base.json`. Models are saved in the run's `/kaggle/working/asr-ft/{yo,pcm}` (download with `kaggle kernels output`).

## Right now (handoff, 2 Oct ~20:00 WAT, session 6)
**Done in session 6 (2 Oct):**
- **Kaggle `trainprep` run complete** (read 2 Oct; `results/trainprep/`):
  - **Teacher labels (ADR-0021):** 600 clips (300 yo + 300 pcm) → **460 kept**: 230 with findings, 230 with none. Dropped:
    - 30 invalid (16 cut off mid-JSON);
    - 55 with a quote not found in the clip;
    - 4 not verbatim;
    - 51 empty answers over the half-empty cap.
  - The kept file is restored to `data/private/kaggle/teacher.kept.jsonl` (git-ignored).
  - **Base N-ATLaS few-shot on H (454 hard negatives):**
    - false-alarm rate **0.185**, so the base model invents a finding on about 1 in 5 talks that contain none;
    - 47/454 outputs invalid (42 cut off);
    - recall and rule-flag recall are undefined here (H has no danger signs by construction).
- **50-clip teacher check built** (`scripts/teacher_check.py build`): 25 yo + 25 pcm → `data/private/label_queue.teacher-check.jsonl`. **Malik:** upload it and label it.
- `scripts/kaggle_log.py` no longer crashes on a metric that is undefined for a stratum.
- **Team invited by Malik (2 Oct).** Clinical sign-off progress at ~19:00 WAT:
  - Rahmat 131/131 and Nurse Success 131/131;
  - pharmacist 3/7;
  - Malik 1/131 and Doc Abdullahi 0/131.
- **The scheduled check-ins below were never created as routines** (checked 2 Oct: neither ID exists). Recreate any check-in as a real routine, and confirm it exists.
- **ADR-0024 accepted (2 Oct): the fine-tuning recipe** (Malik: "keep this close"). Two findings from the teacher labels drive it:
  - zero real yo/pcm examples of reduced fetal movement and unconscious, and 2 each of convulsions and severe abdominal pain;
  - `looks_very_ill` over-assigned on patient speech: 42 items, most of them general talk or negations.

  The recipe:
  - **Data:** a concept audit, a clinician-approved rare-sign phrase bank, and N-ATLaS ASR two-view training data.
  - **Training:** safety-weighted SFT, with `maxItems` bounds for every rung (decided before the freeze).
  - **Optional stages:** on-policy DPO, and a LoRA scale chosen on dev for G2.
  - **Shipping:** imatrix Q4.

  Run plan and timeline are in the ADR.
- **ADR-0024 build, done 2 Oct:**
  - **Decoding bounds:** 10 items each on findings, tests and medications, for every rung. Recorded in eval plan §6 before the freeze.
  - **Teacher audit:**
    - 42 `looks_very_ill` labels removed by definition;
    - after the empty cap, 376 teacher items remain (188 with findings, 188 without);
    - dev split by speaker: 319 train / 57 dev, 20 dev speakers, no overlap.
  - **Teacher check scorer:** now gives per-concept precision. The decision applies to the audited labels.
  - **Safety-weighted SFT:** CPU-verified; weights land exactly on concept/assertion tokens, and weight 1 equals the plain loss.
  - **Configs:** runs B (plain) and C (×3), with N-ATLaS pinned at `e294476`.
  - **`build_train_set.py`:** applies the audit, the teacher-check drops and the phrase bank, and writes `sft.v1.jsonl` + `sft.v1.dev.jsonl`.
- **Malik:**
  - correct the draft rare-sign phrase bank `data/train/phrasebank.rare.v0.yaml` (43 yo/pcm entries), then set `approved_by.language`;
  - Rahmat checks the concepts and assertions and sets `approved_by.clinical`.

  The builder refuses the file until both are set.
- **Labelling, 2 Oct evening (admin stats):**
  - benchmark 0/600;
  - practice 3/20 (Success);
  - calibration 0/20;
  - teacher check not uploaded yet.

  The benchmark needs 720 labels by about 8 Oct, so about 60 a day per labeller from 3 Oct.
- **Run A done, 3 Oct (Kaggle version 15; restored to `data/private/kaggle/asr.jsonl`, 1,060 clips, no empty outputs).** Base N-ATLaS ASR, language auto-detected as released, pooled WER vs WazobiaSpeech human transcripts (`results/asr/base-wer.20261003.json`):

  | Language (model) | Test pool | Training clips |
  |---|---|---|
  | Pidgin (NigerianAccentedEnglish) | **51.1%** (300 clips, 1.17 h) | 53.1% (242 clips) |
  | Yoruba (Yoruba-ASR) | **44.7%** (300 clips, 1.36 h) | 36.1% (218 clips) |

  About one word in two is wrong on Pidgin and nearly one in two on Yoruba, so the ASR-input condition is much harder than the transcript condition. This is the evidence for ADR-0026 (health-domain ASR fine-tune; proposed, needs Malik's approval). Next on Kaggle: `PLAN = "checks"` (repetition penalty 1.12 on the pilot items, and auto vs forced language on 30 training clips per language).
- **Run A build notes:**
  - `bench/asr_run.py` transcribes 1,060 clips: 460 training clips and the 600-clip test pool. Only the parquet row groups holding a target are read; shard reads retry.
  - `bench/two_view.py` builds the ASR view of each teacher clip, with evidence moved onto the ASR words.
  - `build_train_set.py --asr` adds those views.
  - **Verified locally on 2 test-pool Pidgin clips:** both found among 86 shards and transcribed.
  - **WER vs human transcript: 42.7% and 55.7%.** Only 2 clips, but a warning: Pidgin goes through NCAIR1's Nigerian-accented English model, so the ASR-input condition will be much harder. Run A gives the real per-language WER over all clips, which is a reportable validation result.
  - **After Run A:** `python scripts/kaggle_log.py --save results/asr` restores `data/private/kaggle/asr.jsonl`.
- **Test queue recovered:** `data/private/label_queue.s4w.jsonl` (600) and `label_queue.s4w-cal.jsonl` (20) were in Malik's Downloads (1 Oct 19:52, the files he uploaded). They are now in `data/private/` on the laptop, so the stage-1 freeze can run from here.
  - Checked: 300 yo + 300 pcm, 35 speakers, no hints, no overlap with the practice set.
  - The review app's database tokens are Vercel "sensitive" variables and cannot be read back, so item-by-item verification against the app is not possible. The counts and the file's provenance match.
- **Still to build:**
  - the stage-2 pair builder and DPO trainer;
  - the scaled merge, GGUF and imatrix;
  - the Yoruba perplexity proxy for choosing the scale;

**Done in session 5:**
- **Results and settings:**
  - Baseline, pilot and pre-freeze runs recorded.
  - Margins G1/G2 approved, with G2 m = 3 points measured.
  - Proposals A–E approved.
  - ADRs 0018–0022 accepted.
- **Data search closed:** HelpMum dropped. MAMAI still refused; Intron and Ajagbe emailed.
- **Review app:**
  - Guided, role-aware flow; phone-first labelling with levels and streaks.
  - Real-speech rules (guidelines §10), enforced server-side.
  - Automatic settling of agreed items; only clinical disagreements go to Rahmat.
  - Gold export.
- **S4-W sets uploaded by Malik:**
  - "Practice · real speech (S4-W)", 20 clips.
  - "Benchmark · real health speech (S4-W)", 600 clips, 20% double-labelled, hints off.
- **Two-stage freeze built** (ADR-0022).
- **Kaggle `trainprep` job pushed** (notebook version 12): teacher labels plus the base model on H.
- **CI fixed;** `scripts/ci_local.sh` added.
- **Other repos:** oye refresh pipeline fixed.

**Waiting on people (only these are human):**
1. **Malik:**
   - ~~Start the Kaggle run~~ (done; complete 2 Oct).
   - ~~Invite the team~~ (done 2 Oct).
   - Upload and label the 50-clip teacher check (~25 min). In the review app: Admin → Add a labelling set, title "Check · teacher labels", double-labelled 0%, practice off, suggestions off.
   - Say "yes" to the stage-1 freeze on 5 Oct.
2. **Team:** follow *Start here* in the app: guide → sign-off → 20-clip practice → main set.
3. **Rahmat:**
   - Settle disagreements in the app.
   - Confirm the G1 tolerance and the Uyo mapping (both in her sign-off, *Before the freeze*).
4. **Intron / Ajagbe:** replies about data access.

**Scheduled check-ins (this session wakes itself):**
- **2 Oct 06:00 WAT** (`trig_01WvXGqsAeD53xPzKuhqmUmk`):
  - Read the Kaggle log.
  - If the run is done: `kaggle_log.py --save results/trainprep`, record the results, `scripts/teacher_check.py build`, and send Malik the 50-clip file with upload steps.
  - If not done: re-arm in about 3 hours.
- **5 Oct 08:00 WAT** (`trig_01GSBkh1kn7uA3AGx4A2Fd3W`): check MAMAI access, apply ADR-0018, prepare the stage-1 freeze command and ask Malik for "yes".
- **If this session is gone, a new session does the same by hand:**
  - `python scripts/kaggle_log.py`
  - `python scripts/kaggle_log.py --save results/trainprep`
  - `python scripts/teacher_check.py build`, then send the file.

**Takada (ADR-0023, accepted 1 Oct): the health-worker app, live at https://github.com/malikbello/takada-app (private; pushed 1 Oct, redesign v2 on 2 Oct). It is an installable web app (PWA) for Android and iPhone from one codebase; a native wrapper (Capacitor) for the app stores is optional later. Phone app (no hub) deployed 2 Oct to https://takada-app.vercel.app (Vercel project takada-app, team hontime2023; deploy steps in takada-app docs/operations.md); live check passed with no console errors.**
- **Design v3.2 "warm care" (2 Oct):**
  - New t-cradle logo; the name is written **tákàdá**.
  - White default with a peach/rose/violet palette; danger crimson is reserved for alerts.
  - Plus Jakarta Sans, bundled offline.
  - React 19 + Framer Motion with lazy-loaded features: first load 162 KB.
  - Glass surfaces with a floating dock; automatic light mode on low-memory phones.
  - The nurse picks her greeting language (Yorùbá merged forms Ẹ káàárọ̀ / Ẹ káàsán / Ẹ káalẹ́, plus Hausa, Igbo, Pidgin, English). **Malik to check the tone marks and the non-Yorùbá forms.**
  - Spec: `docs/design.md` in takada-app.
- **Next for the hub:** a language-identification step so the visit's "Auto" language is detected from the recording.
- **Built:**
  - `packages/clinical`: rules, folding and the visit guide, ported to TypeScript and tested against vectors from phc-scribe's Python reference (`scripts/export_clinical_bundle.py` → `exports/clinical-bundle.json`, vendored with a pinned SHA-256).
  - `packages/protocol`: append-only, hashed visit events; order-independent state; per-device monotonic timestamps.
  - `apps/mobile`: the offline PWA. Capture, danger alerts with referral note, visit guide with follow-ups, summary so far, hold-to-confirm and amend, pairing and sync, 16 kHz WAV recording, draft button. 71 KB gzipped.
  - `apps/server`: hub/cloud service. Pairing with hashed tokens and revocation, verified idempotent sync scoped by facility, WAV upload, prioritised drafting queue with retries, FHIR R4 export, health checks; it also serves the PWA.
  - `deploy/`: Dockerfile, Compose for the clinic hub (HTTPS proxy, optional llama.cpp model), Kubernetes manifests (kubeconform-valid), and CI jobs (image smoke test, Trivy scan, manifest validation). `docs/operations.md`.
- **Verified end to end on 1 Oct (local):** phone → hub → real phc-scribe API (keyword extractor) → draft back on the phone, with evidence and 4 danger rules firing.
- **Open:**
  - Rahmat signs off the visit-guide items (now in her review-app sign-off, step 6).
  - Measure the hub's drafting throughput (load test).
  - Choose the $0 cloud host and the uptime monitor.
  - Verify the Docker image build (blocked locally by the session proxy's certificate; CI builds it).

**Left after that, in order:**
1. Score Malik's teacher check: `scripts/teacher_check.py score <labels export>`. Teacher labels are used only if danger-sign errors ≤ 1 in 5.
2. Stage-1 freeze (5 Oct).
3. Training set: G with a new seed + kept teacher labels → `scripts/build_train_set.py`.
4. QLoRA on Kaggle (lr 1e-4).
5. Labelling done and settled → gold → stage-2 freeze.
6. Score the fine-tuned model vs base on everything.
7. Uyo check once Rahmat confirms the mapping.
8. Benchmark report, model card, dataset card, demo, submission (target 11 Oct).
9. Deferred: ASR WER on the Adeola recordings.

## Snapshot
- **What:** PHC Scribe. An offline-first AI scribe and safety net for Nigerian primary-health-care workers, built on a fine-tuned N-ATLaS.
- **Challenge:** NAIC 2026, **PS3 Sectoral Fine-Tuning: primary healthcare and community health**. Track B (Innovation & Enterprise), individual applicant with ID.
- **Deadline:** **12 Oct 2026, 23:59 WAT.** Target submission is **11 Oct** (one day of buffer).
- **Validation required:** a 500+ example benchmark vs base N-ATLaS on real data, plus a documented API.
- **Architecture:** approved 29 Sept (`docs/architecture.md`, ADRs in `docs/adr/`). **Evaluation:** `docs/eval-plan.md` (thresholds frozen after the pilot, before any training).

## Where things stand (1 Oct, session 5)
| Area | State |
|---|---|
| Benchmark design | **ADR-0016 accepted:** counted 500 = real NigBench-MAMAI speech (test split), labelled in the review app. Supplements: 300 generated notes (G), MamaBench ANC slice (kept, Malik 1 Oct), AMR. MAMAI access **still refused (403, 1 Oct)**: follow up with Intron 2 Oct. **ADR-0018 (Accepted 1 Oct, amended):** if MAMAI is refused by 5 Oct, the counted set is WazobiaSpeech **`dev` + `dev_test`** health clips (yo + pcm, enriched + random groups; about 20 speakers per language, so CIs are wide and the report says so). Its fetcher `scripts/fetch_wazobia.py` is built and tested (queue → `data/private/label_queue.s4w.jsonl`, nothing labelled). Due diligence round 6 (1 Oct): no other real source matches MAMAI; the **Uyo MNCH records** (OSF, CC-BY, 538 real antenatal records, structured) check the rules engine on real vitals (**ADR-0019 accepted**; mapping awaits Rahmat's confirmation). The **Antenatal Orientation Speech Dataset** turned out to be public (GitHub `Adeola80/Antenatal-Speech`, MIT): nurses' clinic talks in en/yo/pcm, usable for ASR tests, phrase mining and hard negatives (needs an ADR). |
| Baseline runs | **Done 30 Sept** (Kaggle run 08:04 UTC → finished between 16:01 and 16:11 UTC, all six runs complete). Results below and in `results/baseline-20260930/`. **Llama-3.1-8B few-shot beats N-ATLaS few-shot on every metric on G**; N-ATLaS few-shot is schema-invalid on 57/300. |
| Pilot | **Done 1 Oct** (see Pilot results). Was run as a saved version started from the notebook editor **1 Oct 13:29 UTC** with `HF_TOKEN` (N-ATLaS few-shot, Llama few-shot, N-ATLaS zero-shot, and a dev-only N-ATLaS few-shot at `max_new_tokens = 1536`, each on the 30 pilot items). The log prints an `=== INVALID` summary per run (how many outputs were cut off). Read it with `scripts/kaggle_log.py`. After it: propose G1/G2 margins → Malik approves → freeze. **G2 set chosen: Belebele `yor_Latn`** (Malik, 1 Oct; `docs/eval-plan.md` §3 and §6). |
| Fine-tuning | Pipeline built and CPU-smoke-tested; **nothing trained.** Order: freeze stage 1 (items, ADR-0022) → generate training G with a **new** seed + real yo/pcm (teacher labels, ADR-0021) → `scripts/build_train_set.py` → `bench/train_qlora.py` on Kaggle → labels adjudicated → freeze stage 2 → score. |
| S4-W labelling | **Uploaded by Malik, 1 Oct; team not yet invited** (labelling count visible only on the admin page). Practice 20 + counted 600 (20% double, hints off). Guidelines §10: the speaker is the patient, general talk is "Nothing to record", skips only for unlabellable clips (enforced server-side on `wazobia` items). Settling is automatic except clinical disagreements, which go to Rahmat (guidelines §10.8). |
| Teacher labels (ADR-0021) | Kaggle `PLAN = "trainprep"` pushed 1 Oct (version 12), **to be started by Malik from the editor**. Then Malik does the blind 50-clip spot check (`scripts/teacher_check.py`). |
| API | `/v1` built (extract, check, records, transcribe with NCAIR1 ASR). Contract `docs/openapi.v1.json`, guide `docs/api.md`. 160 tests pass; CI green. |
| Cloud deploy | **ADR-0017 (Proposed): Modal**, private (proxy auth + API key) until submission, deployed from GitHub Actions. Modal: Starter, $30/month credits, **spend limit $0**. **First successful deploy: 30 Sept 15:21 UTC** (`deploy-modal` run #4, `main` @ `26906eb`) → `https://malikbello--phc-scribe-api-api.modal.run` (keyword extractor, HF ASR). Checked from the cloud session: `/v1/health` and `/v1/extract` without proxy auth return **401**. Still to check (Malik, needs the proxy token + API key): `/v1/health` returns 200 with both, and 401 with proxy auth but no key. Then accept ADR-0017. |
| Review app | Live at https://phc-scribe-review.vercel.app (Vercel project `phc-scribe-review`, Upstash Redis; deploys from `main`). **1 Oct: guided flow, phone-first labelling (one step at a time, levels, streaks), real-speech rules, automatic settling with a "Settle disagreements" step for the clinician (`/adjudicate/[queueId]`), gold export (`kind=gold`).** Each reviewer's home screen has a *Start here* checklist (guide → sign-off for their role → practice set → benchmark labelling, which shows "opens later" until a non-practice set exists), an in-app guide (`/guide`), a **Pharmacist** role (sees only the new *Medicines* sign-off step: 5 medicines + local names + anything missing), and **practice sets** where everyone labels every item (agreement over all pairs; admin toggle per set). Malik to invite Rahmat (Clinician), Oseni (Annotator) and the pharmacy graduate (Pharmacist). |
| Data survey | Rounds 1–6 in `docs/data-sources-survey.md`. WazobiaSpeech repos were renamed to `Africanvoice/{yoruba,naija,igbo,hausa}_african_voices`; **all four now CC-BY-4.0** (the Yoruba licence was added 30 Sept, in the card text). Pinned 1 Oct: yo `353ea9f`, pcm `2bb5618`. |

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

## Pilot results (30 dev items; 1 Oct, saved run started 13:29 UTC)
Point [95% bootstrap CI]. Reports: `results/pilot-20261001/`. 30 items is a pilot: the CIs are wide.

| Metric | N-ATLaS few-shot (768) | N-ATLaS few-shot (1536) | Llama-3.1 few-shot | N-ATLaS zero-shot |
|---|---|---|---|---|
| Danger-sign recall | 0.600 [0.368, 0.812] | identical | **0.950** [0.833, 1.000] | 0.450 [0.222, 0.684] |
| Micro-F1 | 0.451 [0.318, 0.582] | identical | **0.813** [0.727, 0.895] | 0.276 [0.150, 0.400] |
| False-alarm rate (lower is better) | 0.385 [0.125, 0.667] | identical | **0.000** | 0.077 [0.000, 0.250] |
| Schema-valid | 24/30 | 24/30 | 29/30 | 28/30 |

- **Truncation verdict:** the cap is not the cause. N-ATLaS few-shot fails on the same ~20% of items at 768 and 1536 tokens (5 and 4 cut off mid-JSON, the rest schema violations); valid outputs are short (median about 890 characters) and the failed ones run on to whatever cap is set (up to 5,052 characters at 1536). Likely repetition loops in the base model. The comparator keeps 768.
- Same picture as G: Llama-3.1 few-shot is far stronger than base N-ATLaS; fine-tuning N-ATLaS has a lot of room.
- **Proposed G1/G2 margins** are in `docs/eval-plan.md` §6, awaiting Malik's approval (not frozen).

## Where everything lives
| Thing | Location |
|---|---|
| Code | GitHub `malikbello/phc-scribe` (private), branch `main` (production). Local clone in the cloud session: `/home/user/phc-scribe` |
| Kaggle notebook (baseline + pilot runs) | https://www.kaggle.com/code/bellomalik/phc-scribe-baseline (private). Output files: notebook → **Output** tab → `preds/*.jsonl` and `*.report.json` |
| Kaggle code bundle | private dataset https://www.kaggle.com/datasets/bellomalik/phc-scribe-code (built from `git archive HEAD` by `scripts/kaggle_push.py`; no private data) |
| Kaggle job source | `kaggle/baseline/run.py` (`PLAN` switch) + `kernel-metadata.json` (T4, internet on, private) |
| Kaggle secrets | **Runs started through the API (`scripts/kaggle_push.py`) do not receive the `HF_TOKEN` secret** (pilot versions 5–7 on 30 Sept all reported it missing, including one pushed after Malik switched it on). Push the code with `kaggle_push.py`, then **start the run from the notebook editor**: Edit → Add-ons → Secrets (HF_TOKEN on) → Save Version → Save & Run All. In `pilot` mode the job exits within a minute if the token is missing. |
| Reading the Kaggle log from a cloud session | `python scripts/kaggle_log.py [--save results/<run>]`: prints status, `=== INVALID` lines and a metric summary per report, and can save each report JSON. The log is only complete after the run ends. |
| WazobiaSpeech fallback queue (ADR-0018) | `python scripts/fetch_wazobia.py [--check-speakers]` → `data/private/wazobia/*_health.jsonl`, `data/private/label_queue.s4w.jsonl` + `.meta.json` (pools, groups, terms, speaker overlap). Enrichment terms and sampling: `bench/label_queue.py` (`ENRICH_TERMS`, `sample_enriched_queue`). Calibration practice set: `python scripts/build_s4w_calibration.py` → `data/private/label_queue.s4w-cal.jsonl`. Both uploaded per Next steps 3 (labelling started 1 Oct; counted only if ADR-0018 triggers on 5 Oct, otherwise a reported supplement). Freeze: `scripts/freeze_test_set.py items|labels` (ADR-0022). |
| Review app | https://phc-scribe-review.vercel.app; source `review-app/`; env vars `SESSION_SECRET`, `REVIEWERS` (Malik's admin code is in `REVIEWERS` in the Vercel dashboard) |
| Modal deploy | `deploy/modal_app.py` (set `PRIVATE = False` on submission day), workflow `.github/workflows/deploy-modal.yml` (manual: Actions → deploy-modal → Run workflow) |
| GitHub secrets (Actions) | `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `HF_WRITE_TOKEN` (spare; was for the HF Space), `HF_READ_TOKEN`, `PHC_API_KEY` (Malik keeps the key in his password manager; services only ever get its SHA-256 hash) |
| Decisions | `docs/adr/0001`–`0022` (0016 accepted 30 Sept; **0018–0022 accepted 1 Oct**; 0017 proposed) |
| Hard negatives (ADR-0020) | `python scripts/build_adeola_items.py` → `data/bench/h.adeola.jsonl` (454 items, MIT notice in `h.adeola.LICENSE`); source files checksum-pinned, cached in `data/private/adeola/` (incl. the three MP3s for the ASR test) |
| Belebele (G2) | `python -m bench.belebele --model ... --out ...` (zero-shot letter likelihood, pinned revision); runs on Kaggle with `PLAN = "prefreeze"` |
| Fine-tuning evidence | `docs/research/finetuning-review.md` (1 Oct): the literature behind the training recipe and margins; proposals A–E approved 1 Oct |
| Uyo rules check (ADR-0019) | `bench/uyo.py` (fixed mapping, exact CIs; tested), `python scripts/check_uyo.py` (prints the mapping; scores only with `--confirmed-by <adviser>`); data pinned by SHA-256 under `data/private/uyo/` |
| Settling and gold (review app) | Rules: `review-app/src/lib/adjudicate.ts` (single / agreed / majority without a danger-sign split; everything else to the clinician). Clinician screen `/adjudicate/[queueId]`; admin *Gold labels* panel (counts, causes, rule pointers); export `/api/admin/export?kind=gold&queue=<id>` → `python scripts/build_s4_items.py <gold> --set s4w --strict` → `data/bench/s4w.jsonl` + `s4w.excluded.txt` |
| Teacher labels | `bench/teacher.py` (fetch train clips, ADR-0021 filter), `bench/wazobia.py` (text-only reader), Kaggle `PLAN = "trainprep"`; results come back through the log: `python scripts/kaggle_log.py --save results/trainprep` → `data/private/kaggle/teacher.kept.jsonl`. Spot check: `python scripts/teacher_check.py build` / `score <labels export>` |
| Freeze | `scripts/freeze_test_set.py items <files>` (stage 1) / `labels --labelled <queue>=<gold> [--exclude …]` (stage 2); `bench/freeze.py`; manifest `data/bench/test-manifest.json` (ADR-0022) |
| Benchmark data | `data/bench/g.20261002.jsonl` (300, test supplement G), `data/bench/pilot.20261004.jsonl` (30, dev), `tests/fixtures/smoke_items.jsonl` (6, constructed); private queues in `data/private/` (git-ignored) |

## Next steps, in order
1. ~~**Baseline results**~~ **(done 30 Sept; see Baseline results):** read the Kaggle log when the run ends; put the three reports (N-ATLaS few-shot, Llama-3.1 few-shot, N-ATLaS zero-shot on G) in this file. If the 12 h limit cut the last run, re-run only what is missing.
2. ~~**Pre-freeze Kaggle run**~~ **(done 1 Oct; m = 3 points):** Malik starts it from the notebook editor (Save Version → Save & Run All). It scores N-ATLaS and Llama-3.1 on Belebele `yor_Latn` (G2 margin m) and runs the unconstrained base comparator on the pilot items (B). Read with `scripts/kaggle_log.py` (`=== BELEBELE` lines). Then fill m in `docs/eval-plan.md` §6, get Rahmat's G1 confirmation, and commit the freeze. Margins and proposals A–E were approved by Malik on 1 Oct. (Done so far: reports recorded, truncation settled, cap stays 768; originally: propose G1 (false-alarm margin) and G2 (Belebele `yor_Latn` regression margin) in `docs/eval-plan.md` §6 → Malik approves → commit the freeze. G2 needs a Belebele scoring job on Kaggle for base N-ATLaS (not built yet).
3. **S4-W labelling (started 1 Oct, Malik: "label wazobia now")**. Rules: annotation guidelines §10; ADR-0018 amendment 2.
   - **Both sets uploaded by Malik (1 Oct):**
     - "Practice · real speech (S4-W)": 20 clips, practice set.
     - "Benchmark · real health speech (S4-W)": 600 clips, 20% double-labelled, hints off.
   - **Human-only work:**
     - the team labels;
     - Rahmat settles the disagreements that need clinical judgement ("Settle disagreements" on her home screen, answers anonymised).
   - **Everything else is automatic** (guidelines §10.8):
     - single, agreed and danger-safe majority items settle by rule;
     - the admin page groups disagreements by cause and names the rule behind each;
     - if a rule causes repeated disagreements, revise §10 before much of the counted set is done.
   - **Gold:** Admin → set → *Gold (JSONL)* → `python scripts/build_s4_items.py <gold file> --set s4w --strict` → `data/bench/s4w.jsonl` + `s4w.excluded.txt` (ids for the stage-2 `--exclude`).
3b. **Freeze, two stages (ADR-0022, accepted 1 Oct):**
   - **Stage 1** on 5 Oct, after the MAMAI decision: `python scripts/freeze_test_set.py items data/bench/g.20261002.jsonl data/bench/h.adeola.jsonl data/private/label_queue.s4w.jsonl` (plus the MamaBench slice, if built, or the MAMAI queue instead of S4-W if it arrives). Commit the manifest, then `scripts/build_train_set.py` can run.
   - **Stage 2** when labelling is adjudicated: `python scripts/freeze_test_set.py labels --labelled data/private/label_queue.s4w.jsonl=data/bench/s4w.jsonl [--exclude …]`. This must happen before any fine-tuned model sees a counted item.
3c. **Kaggle `trainprep` (pushed 1 Oct, version 12; Malik starts it from the editor):** teacher labels → Malik's blind 50-clip check (`scripts/teacher_check.py build`, upload as "Check · teacher labels", 0% double, practice off, suggestions off; then `score`) → keep or drop teacher labels by the 1-in-5 rule. Base N-ATLaS on H is scored in the same run.
4. **Training data and QLoRA run** on Kaggle (split long jobs so each stays well under 12 h): after stage 1, `scripts/build_train_set.py` on G (new seed) + `data/private/kaggle/teacher.kept.jsonl` if the check passes.
5. **Modal:** ~~run `deploy-modal`~~ (done 30 Sept 15:21 UTC; unauthenticated requests refused), check `/v1/health` and that requests without proxy auth and without the API key are refused; Malik accepts ADR-0017.
6. **MAMAI or the fallback (decide 5 Oct):** if MAMAI access arrives, `scripts/fetch_mamai.py` → upload `label_queue.s4.jsonl` in the review app → the team labels (~9–10 h for 500). If not, and ADR-0018 is accepted, `scripts/fetch_wazobia.py` → upload `label_queue.s4w.jsonl` instead. Either way, the set counted is the one in the freeze; nothing is swapped in afterwards.
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
- **Before every push: `./scripts/ci_local.sh`** (now enforced: `.githooks/pre-push` runs it and blocks the push on any failure). It builds `.venv` from `requirements/ci.lock` with Python 3.12 (CI's exact pinned, hash-checked versions) and runs CI's exact steps, including the review app. Do not trust a system-wide `ruff`/`pyright`: on 1 Oct a newer local ruff passed code that CI's pinned ruff 0.16.9 rejected, and `main` was red for six pushes.
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
| Invite Rahmat (Clinician), Oseni (Annotator) and the pharmacy graduate (Pharmacist) in the review app; send each their code privately | Pending (Malik, 1 Oct) |
| Start the Kaggle `trainprep` run from the notebook editor (HF_TOKEN attached) | **Running** (started by Malik; checked 2 Oct ~00:30 WAT) |
| Check the Yorùbá tone marks in Takada (Ẹ káàárọ̀ / Ẹ káàsán / Ẹ káalẹ́ / Ẹ káàbọ̀) and get the Hausa, Igbo and Pidgin greetings checked | Pending (Malik) |
| Try Takada on a real iPhone and Android phone: https://takada-app.vercel.app (iPhone: Safari → Share → Add to Home Screen; Android: Chrome → Install app) | Pending (Malik) |
| Delete the stray Vercel project `dist` (dist-one-woad-17.vercel.app), created by a mis-targeted deploy on 2 Oct; it serves the same public app build, no data | Pending (Malik to approve deletion) |
| Choose the $0 host for the Takada cloud server and the uptime monitor | Pending (Malik decides) |
| Label the 50-clip teacher check when it arrives (~25 min) | Pending (Malik; file sent by the 2 Oct check-in) |
| Say "yes" to the stage-1 freeze on 5 Oct | Pending (Malik) |
| Confirm Rahmat, Oseni and the pharmacy graduate as named team members (Track B needs 2–5); add the pharmacist's name to Team | Pending |
| Follow up with Intron on NigBench-MAMAI access (2 Oct); fallback 5 Oct | Pending |
| Accept or reject ADR-0018 (WazobiaSpeech as the real-data fallback, replacing MamaBench + G) | **Accepted 1 Oct** (amended: dev + dev_test) |
| Decide proposals A–E in `docs/research/finetuning-review.md` | **Approved 1 Oct**: A applied (`configs/qlora.v0.yaml` lr 1e-4), B built (`--unconstrained`), C and D in the training plan (ADR-0021), E in eval plan §6 |
| Start the pre-freeze Kaggle run from the notebook editor | Done 1 Oct |
| Rahmat confirms the Uyo symptom mapping (`python scripts/check_uyo.py` prints it), then run it with `--confirmed-by` | Pending |
| Ask Rahmat to confirm the G1 tolerance (+5 points of false alarms) | Pending |
| Accept ADR-0017 (Modal) after the first successful deploy | Pending |
| Ask the WazobiaSpeech authors (EqualyzAI / DSN) about the Yoruba licence | Resolved 30 Sept: the card now states CC BY 4.0 |
| Optional: ask the authors of the Antenatal Orientation Speech Dataset (Springer 10.1007/978-3-031-75147-9_11) for access | Optional |
| Agent name | **Decided 1 Oct: Takada, written tákàdá** (trademark and domain check still due before public launch) |
| Email organisers about the team-size mismatch (track cards say 2–5, FAQ says 1–6) | Pending |
| Free ≥25 GB of laptop disk (offline node, demo video) | Pending |
| Nurse review of annotation guidelines, vocabulary and rules (now done in the review app's sign-off) | Pending |
| Review/extend the draft Yoruba forms in `bench/baselines/lexicon.v0.yaml` | Pending |
| Remove day/gate wording from public docs before submission (Claude) | From now |
| Optional: delete the unused `HF_WRITE_TOKEN` on Hugging Face and GitHub | Optional |

## Progress log
**1 Oct, session 5 (Kaggle prep job):**
- `PLAN = "trainprep"` in `kaggle/baseline/run.py`, in this order:
  1. **Teacher labels (ADR-0021):** `bench/teacher.py` fetches 300 Yoruba + 300 Pidgin WazobiaSpeech `train` health clips (40 evenly spaced shards, 80% enriched, seed 20261006), and Llama-3.1-8B few-shot labels them.
     - Only schema-valid labels with every quote found verbatim are kept; no-finding items are at most half.
     - The kept file is written into the log; `python scripts/kaggle_log.py --save results/trainprep` restores it to `data/private/kaggle/teacher.kept.jsonl`, and the counts print as `=== TEACHER`.
  2. **Base N-ATLaS few-shot on the 454 Adeola hard negatives (stratum H)**, scored as usual.
- **Malik starts it from the notebook editor** (Save Version → Save & Run All); expect ~6–8 h.
- After it: Malik spot-checks 50 kept teacher labels in the app (ADR-0021 §4; Malik chose to do it himself, 1 Oct).
- Deferred: ASR WER on the Adeola recordings, which needs the audio on Kaggle.
- `scripts/fetch_wazobia.py` now reads through `bench/wazobia.py` (shared with the teacher fetch).

**1 Oct, session 5 (settling disagreements):**
- Malik: keep only truly human tasks human. The review app now settles labels by rule (single, agreed, majority with no danger-sign split) and sends only clinical disagreements to Rahmat (`review-app/src/lib/adjudicate.ts`, `/adjudicate/[queueId]`, home-screen step, admin *Gold labels* panel with causes, `kind=gold` export).
- `scripts/build_s4_items.py --set s4w --strict` builds the S4-W gold file and its exclusion list. 31 app tests and the Python suite pass.

**1 Oct, session 5 (S4-W labelling and the two-stage freeze):**
- CI on `main` is green again (run 36901141065, `d058d09`).
- Malik: "label wazobia now", done the way mature teams do it:
  - **Labelling rules:** annotation guidelines §10 (patient-speech rules), mirrored in the in-app guide, a *Real speech* banner and the label pop-up.
  - **App rules:** the review app refuses off-topic skips on `wazobia` items (server-side, tested).
  - **Hints off:** `scripts/fetch_wazobia.py` now defaults to no hints, and the queue was stripped of them.
  - **Calibration set:** 20 clips from `scripts/build_s4w_calibration.py`.
  - **Records:** ADR-0018 amendment 2.
- **ADR-0022 (two-stage freeze) accepted and implemented:**
  - `bench/freeze.py` (`freeze_items`, `freeze_labels` with declared exclusions, `load_gold_items`);
  - `scripts/freeze_test_set.py items|labels`;
  - tests;
  - eval plan §3 updated.
- `./scripts/ci_local.sh` passes.

**1 Oct, session 5 (CI fix):**
- CI on `main` was red from `de25ff8` to `7fe2a5d` (job `checks`, RUF100: an unused `noqa` that only CI's pinned ruff 0.16.9 reports). Fixed, and `scripts/ci_local.sh` added so local checks use CI's exact versions.

**1 Oct, session 5 (pre-freeze run):**
- Pre-freeze Kaggle run complete (`results/prefreeze-20261001/`). **Belebele `yor_Latn`: N-ATLaS 42.78%, Llama-3.1 34.44%** → G2 margin m = 3 points (50% of the 8.3-point gain is 4.2; the 3-point cap is stricter). **Unconstrained base comparator: 10/30 valid** (vs 24/30 constrained), recall 0.40: forced JSON helps the base model, so the primary comparator is the generous one.
- HelpMum dropped as a data route (Malik). Ajagbe emailed by Malik.

**1 Oct, session 5 (final data search):**
- **Search closed** after round 7 (`docs/data-sources-survey.md`): MAMAI has no public substitute. Remaining routes are requests: Intron (MAMAI; Malik emailed and connected on LinkedIn), Ajagbe (email `saajagbe@pgschool.lautech.edu.ng`, his corresponding-author address on a 2025 paper; draft in chat). HelpMum MamaBench access already accepted; `nig-bench` and MAMAI still pending (1 Oct).
- Pre-freeze Kaggle run started from the editor 16:01 UTC; check-in booked for 16:55 UTC.

**1 Oct, session 5 (proposals applied):**
- WazobiaSpeech fallback queue built from `dev` + `dev_test` (600 items; pools yo 5,584 / pcm 5,591 health clips, 20 / 21 speakers); **speaker check over all shards: 0 shared with `train`** in both languages.
- Malik approved proposals A–E and the Adeola data. **ADR-0020** (Antenatal Orientation Speech: stratum H of 454 real hard negatives, ASR test, phrase mining) and **ADR-0021** (Llama-3.1 teacher labels on training-split speech, filtered and spot-checked) accepted.
- Built: `--unconstrained` runner option with `extract_json`; `bench/belebele.py`; Kaggle `PLAN = "prefreeze"`; `scripts/build_adeola_items.py`; QLoRA learning rate 1e-4. 169 tests pass.

**1 Oct, session 5 (decisions and research):**
- Malik: **ADR-0018 accepted**, **ADR-0019 (Uyo rules check) accepted**, **G1/G2 margins approved**. Intron contacted (no reply yet); NigBench access still not granted.
- ADR-0018 amended at acceptance: `dev_test` has only 8 yo / 11 pcm speakers, so the test pool is `dev` + `dev_test` (20 / 21 speakers).
- `docs/research/finetuning-review.md`: the base model's loop is a known effect of forced-JSON decoding (fine-tuning fixes it); Llama-3.1-8B reaches human-level extraction with 43–100 examples at learning rate 1e-4 (ours is 2e-4); a few target-language examples transfer strongly; teacher-model labels work; FDA/EMA margin practice. Five proposals for Malik.
- Antenatal Orientation Speech Dataset located (GitHub, MIT). Uyo check built and tested; not scored yet.

**1 Oct, session 5 (pilot):**
- **Pilot complete** (see Pilot results). The 768 → 1536 token check showed identical results: the cap is not the cause of N-ATLaS's invalid outputs; the comparator keeps 768. G1 (+5 points) and G2 (−3 points) margins proposed in the eval plan, not frozen.

**1 Oct, session 5 (cont.):**
- **Merged to `main`** (fast-forward, 9 commits): baselines, identity guard, ADR-0018, data survey round 5, review-app guided flow. CI green on all four jobs.
- **Review app guided flow** (see Where things stand). 23 app tests; production build checked; screens checked as pharmacist, nurse and admin.
- **Pilot:** API-started runs never receive Kaggle secrets (4 attempts, including one after the secret was ticked); runs must be started from the notebook editor (Save Version → Save & Run All). An interactive editor session was also lost (its log is not readable via the API). The saved version started 13:29 UTC is the one to read.
- **G2 set chosen: Belebele `yor_Latn`** (Malik). Eval plan §3 rewritten to the ADR-0016/0018 strata (it still described the abandoned AMR plan).
- **ADR-0018 groundwork:** `scripts/fetch_wazobia.py` + `sample_enriched_queue` (tests added); dataset revisions pinned; licences re-checked at those revisions.
- **Due diligence round 6** (`docs/data-sources-survey.md`): nothing replaces MAMAI; Uyo MNCH records found (real, CC-BY, structured).
- `scripts/kaggle_log.py` committed (replaces the scratchpad helper).

**30 Sept, session 5:**
- **Modal deployed** (run #4, 15:21 UTC) after the `MODAL_TOKEN_SECRET` fix; unauthenticated `/v1/health` and `/v1/extract` return 401.
- Tokens restored mid-session. **Baselines finished** (all six runs); reports recorded above and committed to `results/baseline-20260930/`.
- Pilot: versions 5 and 6 ran Llama only (29/30 valid; the 1 invalid output was cut off mid-JSON); version 7 stopped early. N-ATLaS never received `HF_TOKEN` through API-started runs.
- ADR-0018 proposed (WazobiaSpeech as the real-data fallback). Data survey round 5.
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
