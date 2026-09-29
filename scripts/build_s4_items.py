"""Turn the S4 queue plus exported labels into gold benchmark items (ADR-0016).

    python scripts/build_s4_items.py data/private/labels/*.jsonl

Several label files can be passed (e.g. Malik's and the nurse's). For each item the
latest label wins, unless --labeller restricts to one person (used to build each
annotator's set for the agreement check). Prints counts and errors only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT), str(ROOT / "scripts")]

from _safe_output import fail, say  # noqa: E402

from bench.items import read_jsonl, write_jsonl  # noqa: E402
from bench.label_queue import Label, QueueItem, build_items  # noqa: E402

QUEUE_PATH = ROOT / "data" / "private" / "label_queue.s4.jsonl"
OUT_PATH = ROOT / "data" / "private" / "bench" / "s4.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", nargs="+", type=Path)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--labeller", help="only use labels by this person")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    queue = list(read_jsonl(args.queue, QueueItem))
    labels = [lab for p in args.labels for lab in read_jsonl(p, Label)]
    if args.labeller:
        labels = [lab for lab in labels if lab.labeller == args.labeller]
    items, report = build_items(queue, labels)
    write_jsonl(args.out, items)
    say(
        f"{report.items} gold items -> {args.out}; skipped {report.skipped},"
        f" unlabelled {report.unlabelled}, errors {len(report.errors)}"
    )
    for err in report.errors:
        fail(f"  {err}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
