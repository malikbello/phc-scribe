"""Restore the tokenizer of an uploaded ASR fine-tune from its base model.

    python scripts/fix_asr_tokenizer.py --lang yo
    python scripts/fix_asr_tokenizer.py --lang yo \
        --local data/private/models/asrft-20261003/asr-ft/yo

On 6 Oct the Yoruba repo was uploaded with an empty tokenizer.json and no tokenizer_config.json,
so it cannot be loaded. Fine-tuning does not change the Whisper tokenizer: the Pidgin fine-tune's
vocabulary, merges and added tokens are identical to its base model's (checked 7 Oct), and both
NCAIR1 bases share that tokenizer. This script checks that again, then copies the base model's
tokenizer files into the fine-tuned repo (and, with --local, into the local folder), and checks
that the processor loads from the repo. Needs HF_TOKEN with write access; prints no token.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

REPOS = {
    "yo": ("NCAIR1/Yoruba-ASR", "malikbello/N-ATLaS-ASR-Health-Yoruba-Powered-by-Awarri"),
    "pcm": (
        "NCAIR1/NigerianAccentedEnglish",
        "malikbello/N-ATLaS-ASR-Health-Pidgin-Powered-by-Awarri",
    ),
}
REFERENCE = (
    "malikbello/N-ATLaS-ASR-Health-Pidgin-Powered-by-Awarri"  # a fine-tune with its tokenizer
)
FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "normalizer.json",
    "special_tokens_map.json",
    "added_tokens.json",
)


def core(path: str) -> tuple:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    merges = [tuple(m.split()) if isinstance(m, str) else tuple(m) for m in d["model"]["merges"]]
    added = sorted((t["id"], t["content"]) for t in d.get("added_tokens", []))
    return d["model"]["vocab"], merges, added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=sorted(REPOS), required=True)
    parser.add_argument("--local", type=Path, help="also repair this local model folder")
    args = parser.parse_args()
    from huggingface_hub import HfApi, hf_hub_download

    base, repo = REPOS[args.lang]
    api = HfApi()
    if not api.model_info(repo).private:
        raise SystemExit(f"{repo} is not private: refusing to change it")
    with tempfile.TemporaryDirectory() as tmp:
        base_tok = hf_hub_download(base, "tokenizer.json", local_dir=f"{tmp}/base")
        ref_tok = hf_hub_download(REFERENCE, "tokenizer.json", local_dir=f"{tmp}/ref")
        if core(base_tok) != core(ref_tok):
            raise SystemExit(f"{base}'s tokenizer differs from the reference fine-tune: stopping")
        have = {s.rfilename for s in api.model_info(base).siblings or []}
        out = Path(tmp) / "files"
        out.mkdir()
        for f in FILES:
            if f in have:
                shutil.copy(hf_hub_download(base, f, local_dir=f"{tmp}/base"), out / f)
        info = api.upload_folder(
            repo_id=repo,
            folder_path=str(out),
            commit_message=f"Restore the tokenizer files (identical to {base}'s Whisper tokenizer)",
        )
        print(f"{repo}: tokenizer restored, commit {info.oid}")
        if args.local:
            for f in out.iterdir():
                shutil.copy(f, args.local / f.name)
            print(f"{args.local}: tokenizer restored")
    try:
        from transformers import AutoProcessor  # pyright: ignore[reportMissingImports]
    except ImportError:
        print("check skipped: transformers is not installed here (the hub image checks it)")
        return 0
    proc = AutoProcessor.from_pretrained(repo)
    ids = proc.tokenizer("Ẹ káàárọ̀, ṣé ara yín le?").input_ids
    print(f"check: processor loads from {repo}; {len(ids)} tokens for a test sentence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
