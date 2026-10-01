"""Turn a label queue plus exported labels into gold benchmark items (ADR-0016/0018).

    # S4-W: the review app's gold export (Admin -> set -> "Gold (JSONL)")
    python scripts/build_s4_items.py gold.<set>.jsonl --set s4w --strict

    # MAMAI: raw label exports (latest label per item wins)
    python scripts/build_s4_items.py data/private/labels/*.jsonl

The gold export already holds one settled label per item (agreed, majority or the
clinician's decision; annotation guidelines §10.8), so it is the input for the counted
set. --labeller restricts raw exports to one person (per-annotator sets for agreement).
--strict fails if any queue item is unlabelled or unsettled, which stage 2 of the freeze
needs. Items settled as unlabellable are written to <out>.excluded.txt for the freeze's
--exclude. Prints counts and errors only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT), str(ROOT / "scripts")]

from _safe_output import fail, say  # noqa: E402

from bench.items import Stratum, read_jsonl, write_jsonl  # noqa: E402
from bench.label_queue import Label, QueueItem, build_items  # noqa: E402

SETS: dict[str, tuple[Path, Path, Stratum]] = {
    "s4": (
        ROOT / "data" / "private" / "label_queue.s4.jsonl",
        ROOT / "data" / "private" / "bench" / "s4.jsonl",
        "S4",
    ),
    "s4w": (
        ROOT / "data" / "private" / "label_queue.s4w.jsonl",
        ROOT / "data" / "bench" / "s4w.jsonl",
        "S4W",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", nargs="+", type=Path)
    parser.add_argument("--set", choices=sorted(SETS), default="s4")
    parser.add_argument("--queue", type=Path, help="override the set's queue file")
    parser.add_argument("--labeller", help="only use labels by this person")
    parser.add_argument("--out", type=Path, help="override the set's output file")
    parser.add_argument("--strict", action="store_true", help="fail unless every item is settled")
    args = parser.parse_args()

    queue_path, out_path, stratum = SETS[args.set]
    queue = list(read_jsonl(args.queue or queue_path, QueueItem))
    labels = [lab for p in args.labels for lab in read_jsonl(p, Label)]
    if args.labeller:
        labels = [lab for lab in labels if lab.labeller == args.labeller]
    items, report = build_items(queue, labels, stratum=stratum)
    out = args.out or out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(out, items)
    excluded = out.with_suffix(".excluded.txt")
    excluded.write_text("".join(f"{i}\n" for i in report.skipped_ids), encoding="utf-8")
    say(
        f"{report.items} gold items -> {out}; unlabellable {report.skipped} (-> {excluded.name}),"
        f" unsettled {report.unlabelled}, errors {len(report.errors)}"
    )
    for err in report.errors:
        fail(f"  {err}")
    if args.strict and report.unlabelled:
        fail(f"--strict: {report.unlabelled} items are not labelled or not settled yet")
        return 1
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
