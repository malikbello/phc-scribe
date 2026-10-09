"""Freeze the test set in two stages (docs/eval-plan.md "Freezing"; ADR-0022).

Stage 1, items: before any training data is built. Label queues are fine here.

    python scripts/freeze_test_set.py items data/bench/g.20261002.jsonl \
        data/private/label_queue.s4w.jsonl [more test files ...]

Stage 2, labels: before any fine-tuned model is scored. Each queue is swapped for its
adjudicated, gold-labelled benchmark file, which must hold exactly the same items.

    python scripts/freeze_test_set.py labels \
        --labelled data/private/label_queue.s4w.jsonl=data/bench/s4w.jsonl \
        [--exclude data/private/label_queue.s4w.jsonl=<id>,<id>]

Writes data/bench/test-manifest.json (hashes, counts and paths only, safe to commit).
Stage 1 refuses to overwrite a freeze; stage 2 refuses to run twice and keeps every
stage-1 hash. A frozen test set is never edited.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.freeze import freeze_items, freeze_labels, load_manifest  # noqa: E402

MANIFEST = ROOT / "data" / "bench" / "test-manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["items", "labels"])
    parser.add_argument("files", type=Path, nargs="*", help="stage 1: the test files")
    parser.add_argument(
        "--labelled",
        action="append",
        default=[],
        metavar="FROZEN=LABELLED",
        help="stage 2: replace a stage-1 file (path as in the manifest) by its labelled file",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="FROZEN=ID[,ID...]",
        help="stage 2: item ids adjudicated unlabellable (garbled, cut off), reported",
    )
    parser.add_argument("--out", type=Path, default=MANIFEST)
    args = parser.parse_args()
    if args.stage == "items":
        if not args.files:
            sys.exit("stage 1 needs the test files")
        if args.out.exists():
            sys.exit(f"{args.out} exists: the test set is already frozen (never edit a freeze)")
        manifest = freeze_items(args.files, ROOT)
    else:
        if args.files:
            sys.exit("stage 2 takes no files: map replacements with --labelled FROZEN=LABELLED")
        if not args.out.exists():
            sys.exit("freeze the items first: python scripts/freeze_test_set.py items <files>")
        pairs = [m.split("=", 1) for m in args.labelled]
        drops = [m.split("=", 1) for m in args.exclude]
        if any(len(p) != 2 for p in pairs + drops):
            sys.exit("--labelled and --exclude take FROZEN=VALUE")
        try:
            manifest = freeze_labels(
                load_manifest(args.out),
                ROOT,
                {a: Path(b) for a, b in pairs},
                {a: [i for i in b.split(",") if i] for a, b in drops},
            )
        except ValueError as e:
            sys.exit(str(e))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    total = sum(f.items for f in manifest.files)
    print(f"stage {manifest.stage}: froze {len(manifest.files)} files, {total} items -> {args.out}")
    for f in manifest.files:
        if f.excluded:
            print(f"  {f.frozen_as or f.path}: {len(f.excluded)} items excluded as unlabellable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
