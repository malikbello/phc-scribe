# ADR-0015: Host the public API on a free Hugging Face Space; defer GPU serving

- **Status:** Accepted. Amends ADR-0005 and ADR-0007 (cloud runtime).
- **Date:** 2026-09-29

## Context
PS3 requires a documented API another developer can integrate, and judges check integration on 15–17 Oct. Modal's free tier gives only $1 of credit without a payment method, and it rejected the card offered. The project budget is $0.

## Decision
- Serve the public `/v1` API from a **free Hugging Face Space** (Docker, CPU basic hardware). It uses the **same container image** as the offline laptop node: FastAPI + llama.cpp with the GGUF Q4 model + faster-whisper.
- The fine-tuned model lives in a gated HF model repo. The Space reads it with a Space secret.
- A scheduled GitHub Actions ping keeps the Space awake before and during the judging window. Free Spaces sleep when idle.
- GPU serving (vLLM + LoRA) returns when NAIC acceleration credits (for shortlisted teams) or pilot funding exist. The API contract is unchanged.

## Consequences
- $0 and always on, but slow: roughly minutes per extraction on shared CPU. The docs and video state this plainly, and the benchmark reports latency per runtime.
- One image for the cloud and the edge reduces drift between the two.
- Cold starts after sleep take a few minutes. The keep-warm ping covers the judging window.
