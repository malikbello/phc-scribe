"""G1 sensitivity on the frozen H set (post hoc; docs/results-frozen-tests.md).

python scripts/g1_sensitivity.py <frozen G+S5+H+R items.jsonl> results/final/g1-sensitivity.json
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.harness import score  # noqa: E402
from bench.items import BenchItem, Prediction, read_jsonl  # noqa: E402
from bench.metrics import metric_ratios  # noqa: E402
from bench.stats import Ratio, paired_bootstrap_diff  # noqa: E402
from phc_scribe.encounter import Encounter  # noqa: E402

NOTE = (
    "Invalid outputs score as no flag in the registered metric. worst_case: every invalid output "
    "counts as a false alarm, for every system. repaired: invalid outputs re-parsed after dropping "
    "tests without a result, unnamed `other` medications and duplicate findings. Item-level paired "
    "bootstrap (the registered grouping has only 3 clusters on H)."
)
items_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
SYSTEMS = {
    "base_hf": "results/frozen/base/frozen.pred.jsonl",
    "ft_q4": "results/frozen/natlas-qlora-v1-weighted-fs-q4/frozen.pred.jsonl",
    "ft_hf": "results/frozen/natlas-qlora-v1-weighted-fs/frozen-b8.pred.jsonl",
    "base_q4": "results/frozen/base-q4/frozen.pred.jsonl",
}
items = [i for i in read_jsonl(items_path, BenchItem) if i.stratum == "H"]


def load(path: str) -> list[Prediction]:
    by_id = {p.item_id: p for p in read_jsonl(Path(path), Prediction)}
    return [by_id[i.item_id] for i in items]


def repair(raw: str | None) -> Encounter | None:
    try:
        data = json.loads(raw or "")
    except ValueError:
        return None
    anc = data.get("anc") or {}
    anc["tests"] = [
        t
        for t in anc.get("tests") or []
        if t.get("result") is not None or t.get("value") is not None
    ]
    anc["medications"] = [
        m
        for m in anc.get("medications") or []
        if m.get("medication") != "other" or m.get("name_text")
    ]
    seen, findings = set(), []
    for f in data.get("findings") or []:
        key = (f.get("concept"), f.get("assertion"))
        if key not in seen:
            seen.add(key)
            findings.append(f)
    data["findings"] = findings
    try:
        return Encounter.model_validate(data)
    except ValueError:
        return None


preds = {name: load(path) for name, path in SYSTEMS.items()}
false_alarms: dict[str, dict[str, Ratio]] = {}
summary: dict = {}
for name, ps in preds.items():
    scores = score(items, ps)
    invalid = [p.record is None for p in ps]
    fa = [float(s.pred_has_danger and not s.gold_has_danger) for s in scores]
    worst = [1.0 if bad else x for x, bad in zip(fa, invalid, strict=True)]
    fixed = [
        p.model_copy(update={"record": repair(p.raw_output)}) if p.record is None else p for p in ps
    ]
    fixed_scores = score(items, fixed)
    rep = [float(s.pred_has_danger and not s.gold_has_danger) for s in fixed_scores]
    ones = [1.0] * len(items)
    false_alarms[name] = {
        "as_registered": metric_ratios(scores)["false_alarm_rate"],
        "worst_case": Ratio.of(worst, ones),
        "repaired": Ratio.of(rep, ones),
    }
    summary[name] = {
        "invalid": sum(invalid),
        "still_invalid_after_repair": sum(p.record is None for p in fixed),
        **{k: round(v.value(), 4) for k, v in false_alarms[name].items()},
    }

out = {"note": NOTE, "systems": summary, "ft_q4_minus_base_hf": {}}
for view in ("as_registered", "worst_case", "repaired"):
    iv = paired_bootstrap_diff(false_alarms["base_hf"][view], false_alarms["ft_q4"][view])
    out["ft_q4_minus_base_hf"][view] = {
        "point": round(iv.point, 4),
        "low": round(iv.low, 4),
        "high": round(iv.high, 4),
        "passes_g1": iv.high <= 0.02,
    }
out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out["systems"], indent=1))
print(json.dumps(out["ft_q4_minus_base_hf"], indent=1))
