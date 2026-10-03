"""Build the fine-tuning set from training items, against the frozen test set (ADR-0024).

    python scripts/build_train_set.py data/bench/g.<train-seed>.jsonl \
        --teacher data/private/kaggle/teacher.kept.jsonl \
        [--drop-concepts c1,c2]            # from scripts/teacher_check.py score
        [--phrasebank data/train/phrasebank.rare.v0.yaml] \
        [--asr data/private/kaggle/asr.jsonl]   # Run A: the ASR view of teacher clips
        --out data/train/sft.v1.jsonl      # also writes sft.v1.dev.jsonl

Refuses to run before the test set is frozen (scripts/freeze_test_set.py) or if a frozen
file changed. Then, in this order:
1. teacher labels: the definitional audit (looks_very_ill cannot come from patient
   speech), then whole items with a concept the teacher check dropped;
2. the ASR view of each teacher clip (Run A), evidence moved onto the ASR words; a clip
   whose quotes cannot all be found gets no ASR view (bench/two_view.py);
3. the phrase bank, only once approved, capped at 15% of the set;
4. drops any item that shares a group with, duplicates or nearly duplicates a test item;
5. splits off a dev set by speaker/group (15%); both views of a clip share its group, so
   they land on the same side. Every recipe decision is made on dev.
Prints counts only.
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
from bench.train_data import (  # noqa: E402
    audit_teacher,
    cap_share,
    drop_items_with,
    load_phrasebank,
    split_by_group,
)
from bench.two_view import asr_views  # noqa: E402

MANIFEST = ROOT / "data" / "bench" / "test-manifest.json"
PHRASEBANK_SHARE = 0.15
DEV_FRAC = 0.15


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ex in rows:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", type=Path, nargs="*", help="other training items (e.g. G)")
    parser.add_argument("--teacher", type=Path, help="teacher.kept.jsonl (ADR-0021)")
    parser.add_argument("--drop-concepts", default="", help="comma-separated, from the check")
    parser.add_argument("--phrasebank", type=Path, help="approved rare-sign phrase bank (YAML)")
    parser.add_argument("--asr", type=Path, help="Run A output: ASR text per training clip")
    parser.add_argument("--dev-frac", type=float, default=DEV_FRAC)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    if not args.manifest.exists():
        sys.exit("freeze the test set first: python scripts/freeze_test_set.py <test files>")
    test = load_frozen_items(args.manifest, ROOT)

    items = [i for f in args.files for i in read_jsonl(f, BenchItem)]
    print(f"other items: {len(items)}")
    if args.teacher:
        teacher, report = audit_teacher(list(read_jsonl(args.teacher, BenchItem)))
        print(f"teacher audit: {report.model_dump()}")
        dropped = [c for c in args.drop_concepts.split(",") if c]
        if dropped:
            before = len(teacher)
            teacher = drop_items_with(teacher, dropped)
            print(f"teacher check: dropped {before - len(teacher)} items with {dropped}")
        if args.asr:
            rows = [json.loads(x) for x in args.asr.read_text(encoding="utf-8").splitlines() if x]
            asr = {r["audio_id"]: r["text"] for r in rows if r["split"] == "train"}
            views, two = asr_views(teacher, asr)
            print(f"ASR views: {two.model_dump()}")
            teacher += views
        items += teacher
    if args.phrasebank:
        bank = load_phrasebank(args.phrasebank)
        kept_bank = cap_share(items, bank, PHRASEBANK_SHARE)
        print(f"phrase bank: {len(kept_bank)} of {len(bank)} (cap {PHRASEBANK_SHARE:.0%})")
        items += kept_bank

    train_items, dev_items = split_by_group(items, args.dev_frac)
    train, dropped_train = build(train_items, test)
    dev, dropped_dev = build(dev_items, test)
    for d in dropped_train + dropped_dev:
        print("dropped", d)
    dev_path = args.out.with_name(args.out.stem + ".dev.jsonl")
    write(args.out, train)
    write(dev_path, dev)
    print(f"{len(train)} training examples -> {args.out}")
    print(f"{len(dev)} dev examples -> {dev_path}")
    print(f"{len(dropped_train) + len(dropped_dev)} dropped for overlapping the test set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
