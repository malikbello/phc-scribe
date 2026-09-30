"""Build the fine-tuning set from training items, against the frozen test set.

    python scripts/build_train_set.py data/bench/g.<train-seed>.jsonl [...] \
        --out data/train/sft.v0.jsonl

Refuses to run before the test set is frozen (scripts/freeze_test_set.py) or if a
frozen file changed. Drops any item that shares a group with, duplicates or nearly
duplicates a test item, and reports what it dropped.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.freeze import load_frozen_items  # noqa: E402
from bench.items import BenchItem, read_jsonl  # noqa: E402
from bench.sft import build  # noqa: E402

MANIFEST = ROOT / "data" / "bench" / "test-manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    if not args.manifest.exists():
        sys.exit("freeze the test set first: python scripts/freeze_test_set.py <test files>")
    test = load_frozen_items(args.manifest, ROOT)
    items = [i for f in args.files for i in read_jsonl(f, BenchItem)]
    kept, dropped = build(items, test)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for ex in kept:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    for d in dropped:
        print("dropped", d)
    print(f"{len(kept)} training examples -> {args.out} ({len(dropped)} dropped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
