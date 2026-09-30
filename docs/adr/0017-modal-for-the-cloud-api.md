# ADR-0017: Serve the cloud API on Modal, private until submission

- **Status:** Proposed (Malik: confirm the Modal credit balance and set a budget limit)
- **Date:** 2026-09-30
- **Supersedes:** ADR-0015 (free Hugging Face Space)

## Context
- **ADR-0015 is no longer possible.** On 30 Sept, Hugging Face refused to create the Space: "hosting Gradio and Docker Spaces on free cpu-basic requires a PRO subscription". PRO is paid, and the budget is $0.
- **Malik has a Modal account** (tokens verified on 29 Sept). ADR-0015 recorded that without a payment method Modal's free tier gave only about $1 of credit, and the card offered was rejected. The current balance must be checked in the Modal dashboard.
- The cloud dev sessions cannot reach Modal (its client uses gRPC, which the egress proxy blocks). GitHub Actions can.
- Other teams are competing. Nothing should be public before submission.

## Decision
1. **Modal hosts the `/v1` API** (`deploy/modal_app.py`): one CPU container (1 core, 3 GiB) running the API, the rules engine and the N-ATLaS ASR models, **scaling to zero** when idle, at most one container.
2. **Private until submission.** The endpoint requires Modal proxy auth (`requires_proxy_auth=True`): every request needs a Modal proxy-auth token as well as our API key. On submission day we set `PRIVATE = False` and redeploy.
3. **Deploys run from GitHub Actions** (`.github/workflows/deploy-modal.yml`, manual only). Tokens are GitHub secrets; Modal receives only the API key's SHA-256 hash.
4. **A hard budget limit in Modal** equal to the free credits, so the account can never be charged.
5. **The fine-tuned N-ATLaS extractor** is added when it exists, as a scale-to-zero function, **only if the credits allow**. If they do not, the extractor for the judges runs on the offline laptop node (llama.cpp) behind a Cloudflare Tunnel during the judging window, and the Modal API calls it. The API contract is the same either way.

## Consequences
- $0, provided the budget limit is set. With about $1 of credit, the CPU API fits a few hours of use (testing plus judging); GPU serving of the 8B model does not.
- Scale-to-zero means a cold start (tens of seconds, plus loading ASR weights, which are cached on a Modal volume).
- Records live on the container's disk, so they reset when it stops. That is acceptable for a demo; persistent storage is future work.
- If the credit balance turns out larger (for example the $30/month Starter credits), the fine-tuned model can also run on Modal, and this ADR is amended with the measured cost.
