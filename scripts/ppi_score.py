"""S4-W real-speech scores by stratified prediction-powered inference (ADR-0025).

    python scripts/ppi_score.py \
        --committee data/private/committee/committee.gold.jsonl \
        --triage data/private/committee/committee.triage.jsonl \
        --human data/bench/s4w.jsonl \
        --pred base=results/s4w/base.transcript.pred.jsonl \
        --pred ft_q4=results/s4w/ft-q4.transcript.pred.jsonl \
        --pair ft_q4:base \
        --out results/s4w/ppi.transcript.json

- **Committee gold** covers every item; **human gold** covers the seeded sample in each
  stratum (A and B, from the triage file). `bench/ppi.py` combines them, so the committee's
  bias is removed in expectation, with a cluster bootstrap over speakers within strata.
- **S4-W is secondary (eval plan §6a): estimates and CIs, no pass/fail.**
- **Safety stop (ADR-0025 §6):** human danger signs that the committee missed in the
  stratum-B audit. If the upper 95% bound of that miss rate is above 5%, humans must label
  all of stratum B before PPI is valid. The script then writes the stop to `--out` and
  exits with status 3, without estimates.
- Items settled as unlabellable (`--exclude`, one id per line) are dropped from every
  file, as in the stage-2 freeze.

Prints counts and numbers only, never transcript text.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.harness import score  # noqa: E402
from bench.items import BenchItem, Prediction, read_jsonl  # noqa: E402
from bench.metrics import ItemScore, danger_positives, metric_ratios  # noqa: E402
from bench.ppi import Design, ppi_ci, ppi_paired_diff, safety_stop  # noqa: E402
from phc_scribe.vocab import load_vocabulary  # noqa: E402

METRICS = ("danger_recall", "micro_f1", "false_alarm_rate", "schema_valid_rate")
SAFETY_EXIT = 3


class InputError(ValueError):
    """The inputs do not fit together; nothing is scored."""


def load_triage(path: Path) -> dict[str, dict]:
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return {r["item_id"]: r for r in rows}


def read_exclusions(paths: list[Path]) -> set[str]:
    out: set[str] = set()
    for p in paths:
        out |= {x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()}
    return out


def check_inputs(
    committee: list[BenchItem], human: list[BenchItem], triage: dict[str, dict]
) -> None:
    ids = [i.item_id for i in committee]
    if len(set(ids)) != len(ids):
        raise InputError("duplicate item ids in the committee gold")
    known = set(ids)
    missing_triage = sorted(known - set(triage))
    if missing_triage:
        raise InputError(f"{len(missing_triage)} committee items have no stratum in the triage")
    for item in human:
        if item.item_id not in known:
            raise InputError(f"human item {item.item_id} is not in the committee gold")
        if not triage[item.item_id].get("sampled"):
            raise InputError(
                f"human item {item.item_id} was not in the seeded sample; "
                "PPI needs the random sample only (ADR-0025)"
            )
    if not human:
        raise InputError("no human-labelled items")


def safety(
    committee: dict[str, BenchItem], human: list[BenchItem], triage: dict[str, dict]
) -> dict:
    """Stratum-B audit: items where human gold has a danger sign that committee gold lacks."""
    danger_ids = load_vocabulary().danger_sign_ids
    audited = missed = 0
    for h in human:
        if triage[h.item_id]["stratum"] != "B":
            continue
        audited += 1
        human_danger = danger_positives(h.gold, danger_ids)
        committee_danger = danger_positives(committee[h.item_id].gold, danger_ids)
        if human_danger - committee_danger:
            missed += 1
    return asdict(safety_stop(missed, audited))


def _scores(items: list[BenchItem], preds: list[Prediction]) -> dict[str, ItemScore]:
    return {s.item_id: s for s in score(items, preds)}


def run(
    committee: list[BenchItem],
    human: list[BenchItem],
    triage: dict[str, dict],
    systems: dict[str, list[Prediction]],
    pairs: list[tuple[str, str]],
    *,
    n_resamples: int,
    seed: int = 0,
) -> dict:
    check_inputs(committee, human, triage)
    by_id = {i.item_id: i for i in committee}
    stop = safety(by_id, human, triage)
    ids = [i.item_id for i in committee]
    human_ids = {h.item_id for h in human}
    strata = {i: triage[i]["stratum"] for i in ids}
    out: dict = {
        "n_items": len(ids),
        "n_human": len(human_ids),
        "per_stratum": {
            k: {
                "items": sum(1 for i in ids if strata[i] == k),
                "human": sum(1 for i in human_ids if strata[i] == k),
            }
            for k in sorted(set(strata.values()))
        },
        "safety_stop": stop,
        "systems": {},
        "pairs": {},
    }
    if stop["triggered"]:
        return out
    design = Design.of(ids, strata, {i: by_id[i].group_id for i in ids}, dict.fromkeys(human_ids))
    gold = {}
    for name, preds in systems.items():
        c = _scores(committee, preds)
        h = _scores(human, preds)
        gold[name] = (c, h)
        c_ratios = metric_ratios(list(c.values()))
        h_ratios = metric_ratios(list(h.values()))
        out["systems"][name] = {
            m: {
                "ppi": asdict(ppi_ci(design, c, h, m, n_resamples=n_resamples, seed=seed)),
                "committee_only": c_ratios[m].value(),
                "human_sample_only": h_ratios[m].value(),
            }
            for m in METRICS
        }
    for cand, base in pairs:
        out["pairs"][f"{cand}-{base}"] = {
            m: asdict(
                ppi_paired_diff(
                    design, gold[base], gold[cand], m, n_resamples=n_resamples, seed=seed
                )
            )
            for m in METRICS[:3]
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S4-W scores by stratified PPI (ADR-0025).")
    parser.add_argument("--committee", type=Path, required=True)
    parser.add_argument("--triage", type=Path, required=True)
    parser.add_argument("--human", type=Path, required=True)
    parser.add_argument("--pred", action="append", required=True, help="NAME=predictions.jsonl")
    parser.add_argument("--pair", action="append", default=[], help="CANDIDATE:BASE")
    parser.add_argument("--exclude", type=Path, action="append", default=[])
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    drop = read_exclusions(args.exclude)
    committee = [i for i in read_jsonl(args.committee, BenchItem) if i.item_id not in drop]
    human = [i for i in read_jsonl(args.human, BenchItem) if i.item_id not in drop]
    triage = load_triage(args.triage)
    systems: dict[str, list[Prediction]] = {}
    for spec in args.pred:
        name, _, path = spec.partition("=")
        if not path:
            parser.error(f"--pred needs NAME=path, got {spec!r}")
        systems[name] = list(read_jsonl(Path(path), Prediction))
    pairs = []
    for spec in args.pair:
        cand, _, base = spec.partition(":")
        if cand not in systems or base not in systems:
            parser.error(f"--pair {spec!r} names a system without --pred")
        pairs.append((cand, base))
    try:
        result = run(committee, human, triage, systems, pairs, n_resamples=args.resamples)
    except (InputError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    result["excluded"] = len(drop)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    stop = result["safety_stop"]
    print(
        f"items {result['n_items']}, human {result['n_human']}, "
        f"stratum-B audit {stop['missed']}/{stop['audited']} missed "
        f"(upper bound {stop['upper_bound']:.3f})"
    )
    if stop["triggered"]:
        print("SAFETY STOP: label all of stratum B before scoring (ADR-0025 §6)", file=sys.stderr)
        return SAFETY_EXIT
    for name, metrics in result["systems"].items():
        row = ", ".join(
            f"{m} {v['ppi']['point']:.3f} [{v['ppi']['low']:.3f}, {v['ppi']['high']:.3f}]"
            for m, v in metrics.items()
        )
        print(f"{name}: {row}")
    for name, metrics in result["pairs"].items():
        row = ", ".join(
            f"{m} {v['point']:+.3f} [{v['low']:+.3f}, {v['high']:+.3f}]" for m, v in metrics.items()
        )
        print(f"{name}: {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
