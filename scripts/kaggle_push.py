"""Publish the code bundle to a private Kaggle dataset and start the baseline GPU job.

    python scripts/kaggle_push.py            # bundle + push kernel
    python scripts/kaggle_push.py --bundle-only

The bundle is `git archive HEAD` minus the review app, docs and tools: committed code,
the constructed smoke fixtures and the generated G set. Nothing under data/private (it
is git-ignored) can reach it. Needs the Kaggle CLI and KAGGLE_API_TOKEN in the
environment; the token is never printed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATASET = "bellomalik/phc-scribe-code"
KERNEL_DIR = REPO / "kaggle" / "baseline"
EXCLUDE = ("review-app", "docs", "tools")


def run(*args: str, cwd: Path = REPO) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout  # noqa: S603


def bundle(dest: Path) -> Path:
    if run("git", "status", "--porcelain", "--", "bench", "serve", "schema", "rules", "data/bench"):
        sys.exit("commit your changes first: the bundle is built from HEAD")
    tar = dest / "phc-scribe.tar.gz"
    excludes = [f":(exclude){p}" for p in EXCLUDE]
    run(
        "git",
        "archive",
        "--format=tar.gz",
        "--prefix=phc-scribe/",
        "-o",
        str(tar),
        "HEAD",
        "--",
        ".",
        *excludes,
    )
    return tar


def push_dataset(folder: Path, sha: str) -> None:
    meta = {"title": "phc-scribe-code", "id": DATASET, "licenses": [{"name": "other"}]}
    (folder / "dataset-metadata.json").write_text(json.dumps(meta))
    status = ("kaggle", "datasets", "status", DATASET)
    exists = subprocess.run(status, capture_output=True, check=False).returncode == 0  # noqa: S603
    if exists:
        print(run("kaggle", "datasets", "version", "-p", str(folder), "-m", f"code {sha}"))
    else:
        print(run("kaggle", "datasets", "create", "-p", str(folder)))  # private by default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-only", action="store_true")
    args = parser.parse_args()
    sha = run("git", "rev-parse", "--short", "HEAD").strip()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        tar = bundle(folder)
        print(f"bundle {tar.name} at {sha}: {tar.stat().st_size // 1024} KiB")
        push_dataset(folder, sha)
    if not args.bundle_only:
        with tempfile.TemporaryDirectory() as tmp:
            kdir = Path(tmp) / "k"
            shutil.copytree(KERNEL_DIR, kdir)
            print(run("kaggle", "kernels", "push", "-p", str(kdir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
