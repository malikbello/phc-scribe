"""Summarise review-app label exports: progress, agreement and settling. Counts only.

    python scripts/label_report.py <labels export>.jsonl [--gold <gold export>.jsonl]

Inputs are the review app's exports (Admin -> set -> "Labels (JSONL)" and "Gold (JSONL)").
Prints, with no transcript or evidence text (safe to paste into a chat or a PR):
- per labeller: items labelled, skipped, with a danger sign, and median seconds per item;
- double-labelled items: pairwise agreement on "any danger sign present" (percent and
  Cohen's kappa) and on the exact set of danger signs;
- the gold export: settled items by how they were settled, and items with a danger sign.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from phc_scribe.vocab import load_vocabulary  # noqa: E402

DANGER = load_vocabulary().danger_sign_ids
POSITIVE = {"present", "possible"}


def read(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def danger(label: dict) -> frozenset[str]:
    return frozenset(
        f["concept"]
        for f in label.get("findings", [])
        if f["concept"] in DANGER and f["assertion"] in POSITIVE
    )


def kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Cohen's kappa for two raters on a yes/no question."""
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def report(labels: list[dict], gold: list[dict] | None) -> dict:
    latest: dict[tuple[str, str], dict] = {}
    for lab in sorted(labels, key=lambda x: x.get("labelled_at", "")):
        latest[(lab["item_id"], lab["labeller"])] = lab  # a relabel replaces the earlier one
    by_person: dict[str, list[dict]] = defaultdict(list)
    by_item: dict[str, dict[str, dict]] = defaultdict(dict)
    for (item, who), lab in latest.items():
        by_person[who].append(lab)
        by_item[item][who] = lab

    people = {}
    for who, labs in sorted(by_person.items()):
        done = [x for x in labs if x["status"] == "labelled"]
        secs = [x["elapsed_ms"] / 1000 for x in done if x.get("elapsed_ms")]
        people[who] = {
            "labelled": len(done),
            "skipped": len(labs) - len(done),
            "with_danger_sign": sum(bool(danger(x)) for x in done),
            "median_seconds": round(statistics.median(secs), 1) if secs else None,
        }

    pair_stats = {}
    for a, b in combinations(sorted(by_person), 2):
        both = [
            (by_item[i][a], by_item[i][b])
            for i in by_item
            if a in by_item[i]
            and b in by_item[i]
            and by_item[i][a]["status"] == by_item[i][b]["status"] == "labelled"
        ]
        if not both:
            continue
        yes = [(bool(danger(x)), bool(danger(y))) for x, y in both]
        k = kappa(yes)
        pair_stats[f"{a} + {b}"] = {
            "items_both_labelled": len(both),
            "agree_any_danger_sign": f"{sum(x == y for x, y in yes)}/{len(yes)}",
            "kappa_any_danger_sign": None if k is None else round(k, 3),
            "same_danger_signs_exactly": f"{sum(danger(x) == danger(y) for x, y in both)}"
            f"/{len(both)}",
        }

    out: dict = {
        "items_labelled_by_anyone": len(by_item),
        "items_labelled_by_2_or_more": sum(len(v) >= 2 for v in by_item.values()),
        "labellers": people,
        "agreement": pair_stats,
    }
    if gold is not None:
        how = Counter(g["labeller"].split(":", 1)[-1] for g in gold)
        out["gold"] = {
            "settled_items": len(gold),
            "settled_by": dict(how),
            "skipped_as_unlabellable": sum(g["status"] == "skip" for g in gold),
            "with_danger_sign": sum(bool(danger(g)) for g in gold if g["status"] == "labelled"),
            "danger_signs": dict(Counter(c for g in gold for c in danger(g))),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+", type=Path)
    ap.add_argument("--gold", type=Path)
    args = ap.parse_args()
    labels = [lab for p in args.labels for lab in read(p)]
    print(json.dumps(report(labels, read(args.gold) if args.gold else None), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
