"""Deploy the /v1 API to a PRIVATE Hugging Face Docker Space (run by CI, not by hand).

    HF_WRITE_TOKEN=... HF_READ_TOKEN=... PHC_API_KEY_HASHES=... \
        python scripts/deploy_space.py --space malikbello/phc-scribe-api

Creates the Space as private if it does not exist, sets its secrets, uploads the app,
and refuses to continue if the Space is public: it stays private until submission, and
publishing is a deliberate manual step on the Hugging Face website. Tokens are read from
the environment and never printed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATHS = ["pyproject.toml", "README.md", "NOTICE", "serve", "bench", "rules", "schema"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.sqlite3")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--space", required=True)
    args = parser.parse_args()
    from huggingface_hub import HfApi

    for var in ("HF_WRITE_TOKEN", "HF_READ_TOKEN", "PHC_API_KEY_HASHES"):
        if not os.environ.get(var):
            sys.exit(f"{var} is not set")
    api = HfApi(token=os.environ["HF_WRITE_TOKEN"])

    api.create_repo(args.space, repo_type="space", space_sdk="docker", private=True, exist_ok=True)
    if not api.space_info(args.space).private:
        sys.exit(f"{args.space} is PUBLIC: refusing to deploy. Make it private first.")

    # The Space needs a read token for the gated N-ATLaS ASR models, and the key hashes.
    api.add_space_secret(args.space, "HF_TOKEN", os.environ["HF_READ_TOKEN"])
    api.add_space_secret(args.space, "PHC_API_KEY_HASHES", os.environ["PHC_API_KEY_HASHES"])

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for p in APP_PATHS:
            src = ROOT / p
            if src.is_dir():
                shutil.copytree(src, stage / p, ignore=IGNORE)
            else:
                shutil.copy(src, stage / p)
        shutil.copy(ROOT / "space" / "Dockerfile", stage / "Dockerfile")
        shutil.copy(ROOT / "README.md", stage / "PROJECT_README.md")
        shutil.copy(ROOT / "space" / "README.md", stage / "README.md")  # Space card
        api.upload_folder(
            repo_id=args.space,
            repo_type="space",
            folder_path=str(stage),
            commit_message=f"Deploy {os.environ.get('GITHUB_SHA', 'local')[:7]}",
            delete_patterns=["*"],
        )
    info = api.space_info(args.space)
    print(f"deployed to {args.space} (private={info.private}); it builds in a few minutes")
    return 0 if info.private else 1


if __name__ == "__main__":
    raise SystemExit(main())
