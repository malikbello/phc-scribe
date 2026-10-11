"""Fetch the shipped models into a clinic hub's models volume, once, while online.

    docker compose -f deploy/compose/hub.yml --env-file deploy/compose/hub.env \\
        run --rm -e HF_TOKEN -e HF_HUB_OFFLINE=0 scribe python -m phc_scribe.fetch_models

(takada-app docs/operations.md). Writes, under ``--dest`` (default /models):

- ``takada-anc.gguf``: the fine-tuned N-ATLaS Q4_K_M, after its SHA-256 matches the manifest
  published beside it (so a cut-off or altered download is never served);
- ``asr-ft/yo`` and ``asr-ft/pcm``: the fine-tuned N-ATLaS ASR (ADR-0026), each checked to be
  complete (config, weights and tokenizer files present and not empty);
- the base N-ATLaS English ASR (``NCAIR1/NigerianAccentedEnglish``, gated) into the Hugging Face
  cache under ``HF_HOME`` (``/models/hf`` on the hub), for English visits;
- ``asr-int8/en``, ``asr-int8/yo`` and ``asr-int8/pcm``: the int8 CTranslate2 builds of the three
  speech models (ADR-0032 Tier 2), each checked to be complete. The hub uses one only when
  ``PHC_ASR=ct2`` and ``PHC_ASR_INT8_MODELS`` names it.

The repos are gated (automatic approval): accept the N-ATLaS Terms once on each model page with
the Hugging Face account of HF_TOKEN. The token is used for this run only and never written to
the volume. After this, the hub runs offline (HF_HUB_OFFLINE=1).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

OWNER = "malikbello"
GGUF_REPO = f"{OWNER}/N-ATLaS-Health-ANC-Scribe-GGUF-Powered-by-Awarri"
GGUF_RUN = "natlas-qlora-v1-weighted-fs"
ASR_REPOS = {
    "yo": f"{OWNER}/N-ATLaS-ASR-Health-Yoruba-Powered-by-Awarri",
    "pcm": f"{OWNER}/N-ATLaS-ASR-Health-Pidgin-Powered-by-Awarri",
}
ENGLISH_ASR = "NCAIR1/NigerianAccentedEnglish"  # base model, used as-is for English
ASR_REQUIRED = ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json")
# int8 builds (ADR-0032): (repo, folder in the repo). The fine-tunes carry theirs in ct2-int8/.
ASR_INT8 = {
    "yo": (ASR_REPOS["yo"], "ct2-int8"),
    "pcm": (ASR_REPOS["pcm"], "ct2-int8"),
    "en": (f"{OWNER}/N-ATLaS-ASR-NigerianAccentedEnglish-int8-Powered-by-Awarri", ""),
}
INT8_REQUIRED = ("model.bin", "config.json", "vocabulary.json", "tokenizer.json")
FEATURE_CONFIGS = ("preprocessor_config.json", "processor_config.json")  # either one


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def incomplete(folder: Path, required: tuple[str, ...] = ASR_REQUIRED) -> list[str]:
    return [f for f in required if not (folder / f).is_file() or (folder / f).stat().st_size == 0]


def int8_incomplete(folder: Path) -> list[str]:
    missing = incomplete(folder, INT8_REQUIRED)
    if not any((folder / f).is_file() for f in FEATURE_CONFIGS):
        missing.append(" or ".join(FEATURE_CONFIGS))
    return missing


def fetch_gguf(dest: Path) -> str:
    from huggingface_hub import hf_hub_download

    staging = dest / ".download"
    manifest = json.loads(
        Path(hf_hub_download(GGUF_REPO, f"{GGUF_RUN}.manifest.json", local_dir=staging)).read_text(
            encoding="utf-8"
        )
    )
    target = dest / "takada-anc.gguf"
    present = target.is_file() and target.stat().st_size == manifest["bytes"]
    if present and sha256(target) == manifest["sha256"]:
        return f"{target.name}: already present, SHA-256 matches"
    path = Path(hf_hub_download(GGUF_REPO, manifest["file"], local_dir=staging))
    if path.stat().st_size != manifest["bytes"] or sha256(path) != manifest["sha256"]:
        raise SystemExit(f"{manifest['file']} does not match its manifest: not installed")
    path.replace(target)
    (dest / "takada-anc.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return f"{target.name}: installed, SHA-256 {manifest['sha256'][:12]}… matches the manifest"


def fetch_asr(dest: Path, lang: str) -> str:
    from huggingface_hub import snapshot_download

    folder = dest / "asr-ft" / lang
    snapshot_download(ASR_REPOS[lang], local_dir=folder, ignore_patterns=["ct2-int8/*"])
    if bad := incomplete(folder):
        raise SystemExit(
            f"{ASR_REPOS[lang]}: missing or empty {', '.join(bad)}. Restore it first "
            "(phc-scribe scripts/fix_asr_tokenizer.py), then run this again."
        )
    return f"asr-ft/{lang}: installed and complete"


def fetch_english() -> str:
    from huggingface_hub import snapshot_download

    snapshot_download(ENGLISH_ASR)  # into HF_HOME, where the API looks for it offline
    return f"{ENGLISH_ASR}: in the Hugging Face cache"


def fetch_int8(dest: Path, lang: str) -> str:
    from huggingface_hub import snapshot_download

    repo, sub = ASR_INT8[lang]
    staging = dest / ".download" / f"int8-{lang}"
    snapshot_download(repo, local_dir=staging, allow_patterns=[f"{sub}/*"] if sub else None)
    src = staging / sub if sub else staging
    if bad := int8_incomplete(src):
        raise SystemExit(f"{repo} {sub or '(root)'}: missing or empty {', '.join(bad)}")
    target = dest / "asr-int8" / lang
    shutil.rmtree(target, ignore_errors=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target, ignore=shutil.ignore_patterns(".cache", "README.md", ".git*"))
    return f"asr-int8/{lang}: installed and complete"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=Path("/models"))
    parser.add_argument("--only", choices=["gguf", "asr", "int8"], help="fetch just one kind")
    args = parser.parse_args()
    if not os.environ.get("HF_TOKEN"):
        raise SystemExit("set HF_TOKEN (an account that accepted the N-ATLaS Terms on each repo)")
    args.dest.mkdir(parents=True, exist_ok=True)
    if args.only in (None, "asr"):
        for lang in ASR_REPOS:
            print(fetch_asr(args.dest, lang), flush=True)
        print(fetch_english(), flush=True)
    if args.only in (None, "int8"):
        for lang in ASR_INT8:
            print(fetch_int8(args.dest, lang), flush=True)
    if args.only in (None, "gguf"):
        print(fetch_gguf(args.dest), flush=True)
    shutil.rmtree(args.dest / ".download", ignore_errors=True)
    shutil.rmtree(args.dest / ".cache", ignore_errors=True)
    for lang in ASR_REPOS:
        shutil.rmtree(args.dest / "asr-ft" / lang / ".cache", ignore_errors=True)
    print(
        "done: the hub can now run offline with PHC_EXTRACTOR=llamacpp and PHC_ASR=hf, or with"
        " PHC_ASR=ct2 and PHC_ASR_INT8_MODELS=en=/models/asr-int8/en (ADR-0032)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
