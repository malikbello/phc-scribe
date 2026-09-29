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
- Environment variables: `HF_TOKEN` (HF read token), `KAGGLE_API_TOKEN` (Kaggle `KGAT_…` token; at session start write it to `~/.kaggle/access_token` with mode 600).
- Allowed network: `huggingface.co`, `*.huggingface.co`, `hf.co`, `*.hf.co`, `kaggle.com`, `*.kaggle.com`, `storage.googleapis.com`.
- N-ATLaS gated access: granted on all 5 NCAIR1 repos (N-ATLaS, Hausa/Yoruba/Igbo ASR, NigerianAccentedEnglish).
- Dev container: 4 CPU, ~15 GB RAM, ~30 GB free disk, no GPU.
- **Malik's laptop (offline node):** Dell Latitude 5400, i7-8665U, 16 GB RAM, no usable GPU, Windows 11 + WSL2, Ollama installed. **Disk must be freed to at least 25 GB.**
- **Cloud serving:** Modal was dropped because the virtual card was rejected (ADR-0015). The fallback is a free Hugging Face Space (CPU). Faster options under review: a physical bank debit card on Modal, Lightning AI free credits, or HF ZeroGPU (needs an HF account older than 30 days).

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
| Faster cloud serving (card / Lightning / ZeroGPU) | Malik | Optional, needed by ~day 8 |

## Next steps: days 1–2 (Gate 1)
1. Verify access: HF token (`whoami` + gated N-ATLaS file listing) and Kaggle CLI. Never print tokens.
2. **Data audit** of the African Medical Records dataset: size, visit types (how many ANC?), language, identifiers, license/consent. Write the results to `docs/data-audit.md`.
3. Schema v0 (`schema/encounter.v0.1.json`), aligned to the WHO ANC DAK, with assertion status and evidence spans. Annotation guidelines v0 for the nurse to review.
4. Pick 30 pilot items. Run the **baseline ladder** on a Kaggle GPU (rules baseline, Llama-3-8B-Instruct, base N-ATLaS zero-/few-shot). Measure latency for the Q4 GGUF on CPU.
5. **Gate 1 decision:** does base N-ATLaS show clear, fixable failures, and does the data support ANC scope (or should we use the general-PHC fallback, ADR-0013)?
6. In parallel: repo engineering skeleton + CI; API contract (`/v1`); a design-tokens + clickable-prototype draft (after the name is picked).
