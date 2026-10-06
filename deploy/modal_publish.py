# ruff: noqa: E501  (the model card is a Markdown template; its lines are prose)
"""Upload the shipped Q4 GGUF (run C-fs) from the Modal volume straight to a PRIVATE Hugging
Face model repo, so the ~5 GB file never passes through the laptop.

    modal secret create phc-scribe-hf-write HF_TOKEN=<write token>   # once (or in the Modal dashboard)
    modal run deploy/modal_publish.py --run natlas-qlora-v1-weighted-fs

Checks the file's SHA-256 against the manifest written by deploy/modal_gguf.py before it
uploads, creates the repo private (and refuses to upload if it exists and is public), and
prints the repo id and commit hash, never the token. The name carries the N-ATLaS Terms'
"Powered by Awarri" suffix. Malik switches the repo to gated on submission day (ADR-0015).
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

app = modal.App("phc-scribe-publish")
image = modal.Image.debian_slim(python_version="3.11").pip_install("huggingface_hub[hf_xet]>=0.32")
runs = modal.Volume.from_name("phc-scribe-runs")
SECRETS = [modal.Secret.from_name("phc-scribe-hf-write")]  # HF_TOKEN with write access
REPO = "N-ATLaS-Health-ANC-Scribe-GGUF-Powered-by-Awarri"

CARD = """---
license: other
license_name: n-atlas-terms-of-use
base_model: NCAIR1/N-ATLaS
tags: [gguf, llama.cpp, n-atlas, health, nigeria, antenatal-care]
---

# N-ATLaS Health ANC Scribe · Q4_K_M GGUF · Powered by Awarri

A QLoRA fine-tune of [NCAIR1/N-ATLaS](https://huggingface.co/NCAIR1/N-ATLaS) that drafts structured
antenatal-visit records (and the findings behind danger-sign checks) from Yoruba, Nigerian Pidgin and
English visit transcripts. Built for PHC Scribe, an offline scribe for Nigerian primary health care
(NAIC 2026). Merged, then quantised to Q4_K_M with an importance matrix computed on training text only;
runs offline on a laptop CPU with llama.cpp.

- File: `{file}` ({gb:.2f} GB), SHA-256 `{sha256}`
- Training run: `{run}`; llama.cpp commit `{commit}`

## Frozen-test results (pre-registered; this file vs base N-ATLaS few-shot)
| | Base | This model |
|---|---|---|
| Danger-sign recall, Yoruba | 52.6% | **67.9%** |
| Danger-sign recall, Pidgin | 68.0% | **76.9%** |
| Danger-sign recall, English | 80.2% | **91.0%** |
| False alarms on talks with no danger sign | 15.9% | **9.3%** |

Every pre-registered criterion passes (P1, P2, G1, G2); confidence intervals and methods are in the
PHC Scribe benchmark report.

## Use and limits
- Use with the PHC Scribe prompt and JSON schema; decode greedily with repetition penalty 1.12.
- Danger signs are decided by deterministic rules, not by this model; a health worker confirms every record.
- Licence: the N-ATLaS Terms of Use apply to this derivative (including the "Powered by Awarri" naming
  and the active-user limit without a commercial licence).
"""


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


@app.function(image=image, secrets=SECRETS, volumes={"/runs": runs}, timeout=3 * 3600)
def publish(run: str, owner: str) -> str:
    from huggingface_hub import HfApi

    gguf_dir = Path("/runs") / run / "gguf"
    manifest_path = gguf_dir / f"{run}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    q4 = gguf_dir / manifest["file"]
    print(f"checking {q4.name} ({manifest['bytes'] / 1e9:.2f} GB) against its manifest", flush=True)
    if q4.stat().st_size != manifest["bytes"] or _sha256(q4) != manifest["sha256"]:
        raise SystemExit(f"{q4.name} does not match its manifest: refusing to upload")

    api = HfApi()
    repo = f"{owner}/{REPO}"
    api.create_repo(repo, private=True, exist_ok=True, repo_type="model")
    if not api.model_info(repo).private:
        raise SystemExit(f"{repo} exists and is not private: refusing to upload")
    card = CARD.format(
        file=q4.name,
        gb=manifest["bytes"] / 1e9,
        sha256=manifest["sha256"],
        run=run,
        commit=manifest["llama_cpp_commit"],
    )
    api.upload_file(path_or_fileobj=card.encode(), path_in_repo="README.md", repo_id=repo)
    api.upload_file(
        path_or_fileobj=str(manifest_path), path_in_repo=manifest_path.name, repo_id=repo
    )
    print(f"uploading {q4.name} (this takes a while)", flush=True)
    info = api.upload_file(
        path_or_fileobj=str(q4),
        path_in_repo=q4.name,
        repo_id=repo,
        commit_message=f"Q4_K_M GGUF of {run}",
    )
    return f"{repo}: private, commit {info.oid}"


@app.local_entrypoint()
def main(run: str = "natlas-qlora-v1-weighted-fs", owner: str = "malikbello") -> None:
    print(publish.remote(run, owner))
