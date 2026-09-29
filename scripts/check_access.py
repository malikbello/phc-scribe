"""Verify Hugging Face and Kaggle access (docs/status.md, days 1-2, step 1).

    pip install -e ".[data]"
    python scripts/check_access.py [--model NCAIR1/N-ATLaS ...] [--dataset ORG/NAME]

Checks: tokens present (never printed), HF identity, the gated N-ATLaS repos list
their files, the benchmark source dataset is reachable, and the Kaggle API accepts
the token. Credentials come only from HF_TOKEN and KAGGLE_API_TOKEN (the Kaggle CLI
reads KAGGLE_API_TOKEN directly, so no token file is written). Exit code 0 only if
every check passes.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _safe_output import fail, say

DEFAULT_MODELS = ["NCAIR1/N-ATLaS"]
DEFAULT_DATASET = "Nigeria-Health-data-OCR-pipeline/African-Medical-Records"
WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt")


def _explain(e: Exception) -> str:
    name = type(e).__name__
    text = str(e).splitlines()[0] if str(e) else ""
    if name == "ProxyError" or ("proxy" in text.lower() and "403" in text):
        host = re.search(r"host='([^']+)'", text)
        where = f" to {host.group(1)}" if host else ""
        return f"network policy blocked the connection{where} ({name})"
    return f"{name}: {text[:300]}"


def check_env() -> bool:
    ok = True
    for var in ("HF_TOKEN", "KAGGLE_API_TOKEN"):
        present = bool(os.environ.get(var))
        say(f"  {var}: {'set' if present else 'MISSING'}")
        ok &= present
    return ok


def check_hf(models: list[str], dataset: str) -> bool:
    from huggingface_hub import HfApi

    api = HfApi()
    me = api.whoami()
    say(f"  signed in as: {me.get('name')}")
    ok = True
    for repo in models:
        try:
            info = api.model_info(repo)
            files = api.list_repo_files(repo)
            weights = [f for f in files if f.endswith(WEIGHT_SUFFIXES)]
            gguf = [f for f in files if f.endswith(".gguf")]
            say(
                f"  {repo}: {len(files)} files, {len(weights)} weight files"
                f" ({len(gguf)} GGUF), gated={info.gated}, revision={info.sha}"
            )
        except Exception as e:
            ok = False
            fail(f"  {repo}: FAILED {_explain(e)}")
    try:
        ds = api.dataset_info(dataset, files_metadata=True)
        siblings = ds.siblings or []
        size = sum((s.size or 0) for s in siblings)
        license_ = ds.card_data.get("license") if ds.card_data else None
        say(
            f"  dataset {dataset}: {len(siblings)} files, {size / 1e6:.1f} MB,"
            f" license={license_}, gated={ds.gated}, revision={ds.sha}"
        )
    except Exception as e:
        ok = False
        fail(f"  dataset {dataset}: FAILED {_explain(e)}")
    return ok


def check_kaggle() -> bool:
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    say(f"  signed in as: {api.get_config_value('username')}")
    kernels = api.kernels_list(mine=True, page_size=5) or []
    say(f"  API call ok: {len(kernels)} of your notebooks listed (first page)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", dest="models", help="gated model repo")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    args = parser.parse_args()
    models = args.models or DEFAULT_MODELS

    steps: list[tuple[str, Callable[[], bool]]] = [
        ("Environment", check_env),
        ("Hugging Face", lambda: check_hf(models, args.dataset)),
        ("Kaggle", check_kaggle),
    ]
    results: dict[str, bool] = {}
    for title, step in steps:
        say(f"{title}:")
        try:
            results[title] = step()
        except ImportError as e:
            fail(f"  missing dependency ({e.name}); run: pip install -e '.[data]'")
            results[title] = False
        except Exception as e:
            fail(f"  FAILED {_explain(e)}")
            results[title] = False
    say("Summary: " + ", ".join(f"{k} {'ok' if v else 'FAILED'}" for k, v in results.items()))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
