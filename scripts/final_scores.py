"""Pre-registered verdicts on the frozen tests (eval plan §6a): P1, P2, G1, plus the 2x2.

    python scripts/final_scores.py --items <G+S5+H+R items.jsonl> \
        --base results/frozen/base/frozen.pred.jsonl \
        --ft-q4 results/frozen/natlas-qlora-v1-weighted-fs-q4/frozen.pred.jsonl \
        [--ft-hf ...] [--base-q4 ...] --out results/final/verdicts.json

- **P1:** danger-sign recall, fine-tuned Q4 - base few-shot (HF). The lower 95% paired-bootstrap
  bound must be > 0 in each of Yoruba (S5), Pidgin (S5) and English (G).
- **P2:** micro-F1, same comparison, on S5 (yo, pcm) and G (en).
- **G1:** false-alarm rate on H. The upper bound of the difference must be <= +2 points.
- **Also reported:** every system on every set and language (the 2x2), McNemar on item-level
  danger detection, and R (red team) per item.

S4-W is scored after the stage-2 label freeze, with PPI (`bench/ppi.py`); not here.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.harness import report  # noqa: E402
from bench.items import BenchItem, Prediction, read_jsonl  # noqa: E402

G1_MARGIN = 0.02
SETS = {
    "S5 yo": lambda i: i.stratum == "S5" and i.language == "yo",
    "S5 pcm": lambda i: i.stratum == "S5" and i.language == "pcm",
    "G en": lambda i: i.stratum == "G",
    "H": lambda i: i.stratum == "H",
    "R": lambda i: i.stratum == "R",
}
P1_SETS = ("S5 yo", "S5 pcm", "G en")


def subset(items: Sequence[BenchItem], preds: dict[str, Prediction], keep) -> tuple[list, list]:
    chosen = [i for i in items if keep(i)]
    return chosen, [preds[i.item_id] for i in chosen]


def point(rep: dict, metric: str) -> float | None:
    return rep["overall"].get(metric, {}).get("point")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True, help="primary comparator (HF)")
    parser.add_argument("--ft-q4", type=Path, required=True, help="primary system (llama.cpp)")
    parser.add_argument("--ft-hf", type=Path)
    parser.add_argument("--base-q4", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    items = list(read_jsonl(args.items, BenchItem))
    systems = {
        "base_hf": args.base,
        "ft_q4": args.ft_q4,
        "ft_hf": args.ft_hf,
        "base_q4": args.base_q4,
    }
    preds = {
        name: {p.item_id: p for p in read_jsonl(path, Prediction)}
        for name, path in systems.items()
        if path
    }
    for name, by_id in preds.items():
        missing = [i.item_id for i in items if i.item_id not in by_id]
        if missing:
            raise SystemExit(
                f"{name}: {len(missing)} items without a prediction, e.g. {missing[:3]}"
            )

    out: dict = {"sets": {}, "verdicts": {}}
    for set_name, keep in SETS.items():
        entry: dict = {}
        for name in preds:
            chosen, ps = subset(items, preds[name], keep)
            entry[name] = {"n": len(chosen)} | {
                m: point(report(chosen, ps), m)
                for m in ("danger_recall", "micro_f1", "false_alarm_rate", "schema_valid_rate")
            }
        chosen, ft = subset(items, preds["ft_q4"], keep)
        _, base = subset(items, preds["base_hf"], keep)
        entry["ft_q4_vs_base_hf"] = report(chosen, ft, base).get("vs_baseline")
        out["sets"][set_name] = entry

    def diff(set_name: str, metric: str) -> dict:
        return out["sets"][set_name]["ft_q4_vs_base_hf"]["diff"][metric]

    out["verdicts"]["P1"] = {
        s: {**diff(s, "danger_recall"), "passes": (diff(s, "danger_recall")["low"] or 0) > 0}
        for s in P1_SETS
    }
    out["verdicts"]["P2"] = {
        s: {**diff(s, "micro_f1"), "passes": (diff(s, "micro_f1")["low"] or 0) > 0} for s in P1_SETS
    }
    g1 = diff("H", "false_alarm_rate")
    out["verdicts"]["G1"] = {**g1, "margin": G1_MARGIN, "passes": (g1["high"] or 0) <= G1_MARGIN}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["verdicts"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
