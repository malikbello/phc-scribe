"""The ADR-0021 §4 spot check of teacher labels: build the 50-clip set, then score it.

    python scripts/teacher_check.py build      # -> data/private/label_queue.teacher-check.jsonl
    python scripts/teacher_check.py score labels.<set>.<date>.jsonl

`build` draws a seeded random 50 of the kept teacher labels (data/private/kaggle/
teacher.kept.jsonl, saved by scripts/kaggle_log.py --save), half Yoruba and half Pidgin.
The check is **blind**: the queue has no hints, so the checker labels each clip from the
words alone, and `score` compares the two automatically. Nobody reads Llama's answer
first, so nobody is anchored on it.

Upload in the review app: Admin -> Add a labelling set, title "Check · teacher labels",
double-labelled share 0%, practice set off, keyword suggestions off.

`score` takes the set's label export (Admin -> set -> Labels (JSONL)) and reports, per
clip, whether the teacher matched on danger signs (present/possible) and on the full
answer. Decision rule (ADR-0021 §4, fixed before use): teacher labels are used for
training only if at most 1 in 5 checked clips has a danger-sign error. Prints counts only.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT), str(ROOT / "scripts")]

from _safe_output import fail, say  # noqa: E402

from bench.items import BenchItem, read_jsonl, write_jsonl  # noqa: E402
from bench.label_queue import Label, QueueItem  # noqa: E402
from phc_scribe.vocab import load_vocabulary  # noqa: E402

KEPT = ROOT / "data" / "private" / "kaggle" / "teacher.kept.jsonl"
QUEUE = ROOT / "data" / "private" / "label_queue.teacher-check.jsonl"
SEED = 20261007
N = 50
MAX_DANGER_ERROR = 0.2
POSITIVE = {"present", "possible"}


def sample(kept: list[BenchItem], n: int = N, seed: int = SEED) -> list[BenchItem]:
    """Seeded random n, split evenly across languages (any shortfall filled from the rest)."""
    rng = random.Random(seed)  # noqa: S311 (sampling, not security)
    by_lang: dict[str, list[BenchItem]] = {}
    for item in sorted(kept, key=lambda i: i.item_id):
        by_lang.setdefault(item.language, []).append(item)
    for pool in by_lang.values():
        rng.shuffle(pool)
    langs = sorted(by_lang)
    picked = [i for lang in langs for i in by_lang[lang][: n // max(1, len(langs))]]
    rest = [i for lang in langs for i in by_lang[lang] if i not in picked]
    return picked + rest[: n - len(picked)]


def to_queue(items: list[BenchItem]) -> list[QueueItem]:
    return [
        QueueItem(
            item_id=f"tc-{i.item_id}",
            group_id=i.group_id,
            language=i.language,
            source="wazobia",
            source_id=i.item_id,
            transcript=i.transcript,
        )
        for i in items
    ]


def _danger(findings, danger_ids: frozenset[str]) -> set[str]:
    return {f.concept for f in findings if f.concept in danger_ids and f.assertion in POSITIVE}


def _answer(findings) -> set[tuple[str, str]]:
    return {(f.concept, str(f.assertion)) for f in findings}


def score(kept: list[BenchItem], labels: list[Label]) -> dict:
    danger_ids = load_vocabulary().danger_sign_ids
    teacher = {f"tc-{i.item_id}": i for i in kept}
    rows: dict[str, int | float | bool | None] = {
        "checked": 0,
        "unlabellable": 0,
        "danger_errors": 0,
        "full_matches": 0,
    }
    checked = unlabellable = danger_errors = full_matches = 0
    latest: dict[str, Label] = {}
    for lab in labels:
        if lab.item_id in teacher and (
            lab.item_id not in latest or lab.labelled_at >= latest[lab.item_id].labelled_at
        ):
            latest[lab.item_id] = lab
    for item_id, lab in latest.items():
        if lab.status == "skip":
            unlabellable += 1
            continue
        gold = teacher[item_id].gold.findings
        checked += 1
        danger_errors += _danger(lab.findings, danger_ids) != _danger(gold, danger_ids)
        full_matches += _answer(lab.findings) == _answer(gold)
    n = checked
    rows.update(
        checked=checked,
        unlabellable=unlabellable,
        danger_errors=danger_errors,
        full_matches=full_matches,
        danger_error_rate=danger_errors / n if n else None,
        full_match_rate=full_matches / n if n else None,
        use_teacher_labels=bool(n) and danger_errors / n <= MAX_DANGER_ERROR,
    )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--kept", type=Path, default=KEPT)
    b.add_argument("--out", type=Path, default=QUEUE)
    s = sub.add_parser("score")
    s.add_argument("labels", type=Path)
    s.add_argument("--kept", type=Path, default=KEPT)
    args = parser.parse_args()

    if not args.kept.exists():
        fail(f"{args.kept} missing: run scripts/kaggle_log.py --save results/trainprep first")
        return 1
    kept = list(read_jsonl(args.kept, BenchItem))
    if args.cmd == "build":
        picked = sample(kept)
        write_jsonl(args.out, to_queue(picked))
        langs = {lang: sum(1 for i in picked if i.language == lang) for lang in ("yo", "pcm")}
        say(f"teacher check: {len(picked)} of {len(kept)} kept clips {langs} -> {args.out}")
        return 0
    result = score(kept, list(read_jsonl(args.labels, Label)))
    say(json.dumps(result))
    if result["checked"] < N:
        say(f"note: {result['checked']} of {N} clips checked so far")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
