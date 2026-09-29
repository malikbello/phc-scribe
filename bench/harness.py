"""Benchmark harness: run a system over items, then score predictions with CIs.

    python -m bench.harness run --system keyword --items ITEMS.jsonl --out PREDS.jsonl
    python -m bench.harness score --items ITEMS.jsonl --pred PREDS.jsonl \
        [--baseline BASE_PREDS.jsonl] [--out REPORT.json]

Scoring always re-runs grounding on the stored record, so every system is judged by
the same pipeline (eval plan, section 2). Model rungs (2-6) plug in as further
systems once the Kaggle runner exists; the keyword baseline (rung 1) runs anywhere.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict
from pathlib import Path

from bench.baselines import keyword
from bench.items import BenchItem, Prediction, read_jsonl, write_jsonl
from bench.metrics import ItemScore, metric_ratios, score_item, summarise
from bench.stats import Interval, mcnemar_exact, paired_bootstrap_diff
from phc_scribe.encounter import Encounter
from phc_scribe.grounding import ground

Extractor = Callable[[str], Encounter]
SYSTEMS: dict[str, tuple[str, Extractor]] = {
    "keyword": (keyword.SYSTEM_NAME, keyword.extract),
}


def run_system(name: str, extract: Extractor, items: Iterable[BenchItem]) -> list[Prediction]:
    preds: list[Prediction] = []
    for item in items:
        t0 = time.perf_counter()
        try:
            record: Encounter | None = extract(item.transcript)
            error = None
        except Exception as e:  # a crash is scored as a schema-invalid output
            record, error = None, f"{type(e).__name__}: {e}"
        latency_ms = (time.perf_counter() - t0) * 1000
        preds.append(
            Prediction(
                item_id=item.item_id,
                system=name,
                record=record,
                error=error,
                latency_ms=round(latency_ms, 3),
            )
        )
    return preds


def score(items: Sequence[BenchItem], preds: Sequence[Prediction]) -> list[ItemScore]:
    by_id = {p.item_id: p for p in preds}
    missing = [i.item_id for i in items if i.item_id not in by_id]
    if missing:
        raise ValueError(f"{len(missing)} items have no prediction, e.g. {missing[:3]}")
    scores: list[ItemScore] = []
    for item in items:
        pred = by_id[item.item_id]
        grounded = ground(pred.record, item.transcript) if pred.record is not None else None
        scores.append(
            score_item(
                item.item_id,
                item.group_id,
                item.gold,
                grounded.record if grounded else None,
                grounded,
            )
        )
    return scores


def _interval(i: Interval) -> dict[str, float | int | None]:
    def clean(x: float) -> float | None:
        return None if math.isnan(x) else round(x, 4)

    return {
        "point": clean(i.point),
        "low": clean(i.low),
        "high": clean(i.high),
        "n_items": i.n_items,
        "n_groups": i.n_groups,
    }


def report(
    items: Sequence[BenchItem],
    preds: Sequence[Prediction],
    baseline: Sequence[Prediction] | None = None,
) -> dict[str, object]:
    systems = {p.system for p in preds}
    out: dict[str, object] = {"system": sorted(systems), "n_items": len(items)}
    scores = score(items, preds)
    by_language: dict[str, object] = {}
    for lang in sorted({i.language for i in items}):
        subset = [s for s, i in zip(scores, items, strict=True) if i.language == lang]
        by_language[lang] = {k: _interval(v) for k, v in summarise(subset).items()}
    out["overall"] = {k: _interval(v) for k, v in summarise(scores).items()}
    out["by_language"] = by_language
    if baseline is not None:
        base_scores = score(items, baseline)
        groups = [s.group_id for s in scores]
        base_r, cand_r = metric_ratios(base_scores), metric_ratios(scores)
        out["vs_baseline"] = {
            "baseline_system": sorted({p.system for p in baseline}),
            "diff": {
                k: _interval(paired_bootstrap_diff(base_r[k], cand_r[k], groups=groups))
                for k in ("danger_recall", "micro_f1", "false_alarm_rate")
            },
            "mcnemar_item_danger_detection": asdict(
                mcnemar_exact(
                    [s.all_danger_detected for s in base_scores if s.gold_has_danger],
                    [s.all_danger_detected for s in scores if s.gold_has_danger],
                )
            ),
        }
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench.harness")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--system", choices=sorted(SYSTEMS), required=True)
    run_p.add_argument("--items", type=Path, required=True)
    run_p.add_argument("--out", type=Path, required=True)
    score_p = sub.add_parser("score")
    score_p.add_argument("--items", type=Path, required=True)
    score_p.add_argument("--pred", type=Path, required=True)
    score_p.add_argument("--baseline", type=Path)
    score_p.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    items = list(read_jsonl(args.items, BenchItem))
    if args.cmd == "run":
        name, extract = SYSTEMS[args.system]
        n = write_jsonl(args.out, run_system(name, extract, items))
        print(f"wrote {n} predictions to {args.out}")
        return 0
    preds = list(read_jsonl(args.pred, Prediction))
    base = list(read_jsonl(args.baseline, Prediction)) if args.baseline else None
    result = json.dumps(report(items, preds, base), indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result + "\n", encoding="utf-8")
        print(f"wrote report to {args.out}")
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
