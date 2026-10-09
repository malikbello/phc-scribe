# Checkpoint, 9 Oct 2026 (end of session 9): prompt for the next session

Paste the block below into the next session (written for Malik's Windows laptop). The full state is in `docs/status.md` → "START HERE (9 Oct 2026, end of session 9)".

**State of every repo at this checkpoint (9 Oct, 20:05 WAT):**

| Repo | `main` | Session branch `claude/awesome-mccarthy-xk2bgl` |
|---|---|---|
| phc-scribe | `de207f0` | 4 commits ahead = **open PR #27** (ADR-0030 polarity check, ADR-0031 speech gate, `scripts/label_report.py`, START HERE (9 Oct), this file). CI green; waits only for Malik's "yes, merge 27". |
| takada-app | `ac2c6d2` (PRs 1–4 merged) | nothing new |
| scholarship-applications | has everything | nothing new |
| project-archive | has everything | nothing new |

```text
You are continuing the PHC Scribe / Takada project on my Windows laptop (PowerShell). The last session (session 9, a cloud session, 6–9 Oct) left a full handoff. Work like a mature engineering team: verify before acting, test everything, PRs with green CI, honest results.

STEP 0: SYNC BEFORE ANYTHING ELSE. Do not edit, run or build anything until this is done.
The four repos sit side by side under C:\Users\Dell\Downloads\Malik\:
  phc-scribe, takada-app, scholarship-applications, project-archive
(If one is not cloned there, tell me and clone it from github.com/malikbello/<repo>.)
In EACH repo:
  1. git status   (if there are uncommitted local changes, STOP and show me; never discard them)
  2. git fetch origin --prune
  3. Compare main with the session branch claude/awesome-mccarthy-xk2bgl:
     git log --oneline origin/main..origin/claude/awesome-mccarthy-xk2bgl
     git log --oneline origin/claude/awesome-mccarthy-xk2bgl..origin/main
  4. git checkout main; git pull --ff-only
  5. Report a short table per repo: local branch, last commit, what the session branch has that main does not, any open PRs.
What you should find (as of 9 Oct, 20:05 WAT):
  - phc-scribe: main = de207f0. The session branch is ahead, = open PR #27 (ADR-0030 polarity check, ADR-0031 speech gate, scripts/label_report.py, the new START HERE (9 Oct) handoff, this checkpoint file). CI green; it waits ONLY for my "yes, merge 27".
  - takada-app: main = ac2c6d2 (PRs 1–4 merged). The session branch has nothing new.
  - scholarship-applications and project-archive: main has everything. The session branches are behind only.
If anything differs (new commits, PR 27 merged or closed, conflicts), say so first, before doing anything else.

STEP 1: READ THE HANDOFF (in this order)
  1. phc-scribe docs/status.md, the section "START HERE (9 Oct 2026, end of session 9)". Until PR #27 is merged that section exists ONLY on the session branch, so read it with:
     git -C phc-scribe show origin/claude/awesome-mccarthy-xk2bgl:docs/status.md
     It lists: what was done, the decisions waiting for me, the exact next steps with commands, what each environment can do, and a prompt per zone. The older "Earlier START HERE (7 Oct)" holds the hub commands.
  2. takada-app docs/status.md and docs/reviews/2026-10-07-pilot-readiness.md (13 blockers fixed; open findings O1–O9; the dry-run checklist).
  3. phc-scribe docs/adr/0030-polarity-check-on-findings.md and 0031-speech-gate-before-asr.md (on the session branch until PR 27 merges).
  4. scholarship-applications README.md (only if I ask about scholarships).

STEP 2: WORKING AGREEMENT (non-negotiable)
  - Commits as: malikbello <139644523+malikbello@users.noreply.github.com>. NO AI attribution anywhere: no co-author lines, no "Generated with" footers, no "claude" in commit or merge messages. The .githooks/commit-msg guard rejects them, so write plain merge messages.
  - No secrets in chat, code, logs or commits. Read tokens from the environment; never print them.
  - $0 spend unless I approve. ADRs for architecture changes. Honest results, including failures.
  - NEVER score the frozen test sets to choose or tune anything (ADR-0022). Dev and pilot data only for development.
  - data/private/ stays on the laptop and is never committed (labels, queues, transcripts).
  - Run ./scripts/ci_local.sh (phc-scribe and takada-app) before every push. PR → green CI → merge.
  - Ask me before anything outward-facing or irreversible: the stage-2 freeze, merging PR 27, making any repo or HF model public, submitting.
  - Scholarships: AI never writes essay answers.

STEP 3: WHERE WE LEFT OFF (9 Oct)
  - Labelling: I finished S4-W labelling on 9 Oct. Nothing has been exported or checked yet.
  - Pilot day was 9 Oct. Ask me how it went (time per record, problems, demo recording) and log it.
  - Waiting on me: (a) "yes, merge 27"; (b) "yes freeze"; (c) the G1 false-alarm tolerance: the nurses asked for +2 points instead of +5. Decide before S4-W scoring.
  - Data access: Intron NigBench-MAMAI and nig-bench are still "awaiting review" (8 Oct). WazobiaSpeech is not open to my HF account.

STEP 4: WHAT TO DO, IN ORDER (the laptop can reach data/private, Modal and Docker; the cloud could not)
  1. Labels: guide me through exporting them from https://phc-scribe-review.vercel.app/admin → the S4-W set → "Labels (JSONL)" and "Gold (JSONL)" into data\private\review\.
     Then run (if PR 27 is not merged yet, first: git checkout origin/claude/awesome-mccarthy-xk2bgl -- scripts/label_report.py):
       .venv\Scripts\python scripts\label_report.py data\private\review\labels.<set>.<date>.jsonl --gold data\private\review\gold.<set>.<date>.jsonl
     Check: everyone's quota (me 120, Rahmat 18, Success 18), agreement and kappa on danger signs, nothing unsettled (no ".partial" gold). Report the counts. It prints no transcript text.
  2. After my "yes freeze": build_s4_items.py --set s4w --strict, then freeze_test_set.py labels (exact commands are in START HERE step 3). Commit only data/bench/test-manifest.json.
  3. CRITICAL PATH: write scripts/ppi_score.py (it does not exist yet). It combines the committee gold on every item with the human gold on the sample, through bench/ppi.py (ADR-0025), with tests. Then score S4-W on transcript input and on ASR input (base and fine-tuned ASR), and write the results doc.
  4. If I said yes to PR 27: merge it (plain message), mark ADR-0030 and ADR-0031 Accepted, then rebuild the hub image:
       docker build -f ../phc-scribe/deploy/api.Dockerfile -t phc-scribe-api:local ../phc-scribe
     Then restart the hub (takada-app deploy/compose, --profile model).
  5. Pilot follow-up: triage what happened like the 7 Oct review (reproduce → fix with tests → PR → merge when green). Re-measure the polarity check on pilot transcripts if I share them (dev use only).
  6. 10 Oct: benchmark report (frozen results + S4-W + as-shipped ASR), error taxonomy (eval plan §7, including review findings O1 and O2), model and dataset cards, technical docs.
  7. 11 Oct: submission checklist; switch the HF repos from private to gated ONLY on my explicit approval. I submit. Deadline 12 Oct 23:59 WAT.

STEP 5: BEFORE YOU STOP (every work block)
  Update phc-scribe docs/status.md START HERE (and takada-app docs/status.md if Takada changed): what you did, the results with file paths, what is waiting for me, the exact next commands, and the resume prompt. Commit, push, and open or update the PR, so the next session can start from the file alone.

Start now with STEP 0, then give me the sync table and a 5-line summary of where things stand before doing anything else.
```
