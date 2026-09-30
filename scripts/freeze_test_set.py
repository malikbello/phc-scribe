"""Freeze the test set before any training data is generated (docs/eval-plan.md).

    python scripts/freeze_test_set.py data/bench/g.20261002.jsonl [more test files ...]

Writes data/bench/test-manifest.json (file hashes and item counts only, safe to commit).
Refuses to overwrite an existing freeze: a frozen test set is never edited.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.freeze import freeze  # noqa: E402

MANIFEST = ROOT / "data" / "bench" / "test-manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, default=MANIFEST)
    args = parser.parse_args()
    if args.out.exists():
        sys.exit(f"{args.out} exists: the test set is already frozen (never edit a freeze)")
    manifest = freeze(args.files, ROOT)
    args.out.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    total = sum(f.items for f in manifest.files)
    print(f"froze {len(manifest.files)} files, {total} items -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
