"""Error taxonomy (eval plan §7): what kinds of mistakes each system makes on the frozen tests.

    python scripts/error_taxonomy.py --out results/errors/taxonomy.20261011.json

Reads the frozen-test predictions after the verdicts were final (docs/results-frozen-tests.md)
and chooses nothing: no model, prompt or threshold depends on it. Every error on G, S5, H and R
gets a category from fixed definitions (below); then a seeded random sample of 50 items with
an error per system is drawn, as the plan says, and categorised the same way. Writes counts
and item ids only (no text); docs/error-taxonomy.md is the written account.

Categories (an item can hold several; its primary category is the first that applies):
1. invalid output: the record failed the schema.
2. missed danger sign, split by what the system wrote instead: nothing; a milder symptom of
   the same family (headache for severe headache); or the sign marked absent.
3. false danger sign, split by what gold holds: the sign denied (absent); a milder symptom of
   the same family; the sign in a past pregnancy; or nothing.
4. measurement: blood pressure or gestational age wrong or missing.
5. other finding: a non-danger concept missed, added or given the wrong assertion.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.items import BenchItem, Prediction, read_jsonl  # noqa: E402
from bench.metrics import score_item  # noqa: E402
from phc_scribe.encounter import POSITIVE_ASSERTIONS, Encounter  # noqa: E402
from phc_scribe.vocab import load_vocabulary  # noqa: E402

SETS = [
    "data/bench/g.20261002.jsonl",
    "data/bench/s5.20261004.jsonl",
    "data/bench/h.adeola.jsonl",
    "data/bench/r.20261004.jsonl",
]
SYSTEMS = {
    "base N-ATLaS few-shot (comparator)": "results/frozen/base/frozen.pred.jsonl",
    "fine-tuned Q4 (shipped)": "results/frozen/natlas-qlora-v1-weighted-fs-q4/frozen.pred.jsonl",
}
# Milder symptoms of the same family as each danger sign (vocabulary ids).
MILDER = {
    "severe_headache": {"headache"},
    "severe_abdominal_pain": {"abdominal_pain", "pelvic_pain"},
    "severe_vomiting": {"nausea_vomiting"},
    "swelling_face_hands": {"leg_oedema"},
    "vaginal_bleeding": {"abnormal_vaginal_discharge"},
    "leaking_amniotic_fluid": {"abnormal_vaginal_discharge"},
    "breathing_difficulty": {"cough"},
    "blurred_vision": {"dizziness", "headache"},
    "severe_pallor": {"fatigue", "dizziness"},
    "unconscious": {"dizziness"},
    "looks_very_ill": {"fatigue"},
}
SAMPLE, SEED = 50, 20261011


def _assertions(record: Encounter | None) -> dict[str, str]:
    if record is None:
        return {}
    return {str(f.concept): str(f.assertion.value) for f in record.findings}


def item_errors(item: BenchItem, pred: Encounter | None, danger: frozenset[str]) -> list[str]:
    if pred is None:
        return ["invalid output"]
    gold, got = _assertions(item.gold), _assertions(pred)
    positive = {str(a.value) for a in POSITIVE_ASSERTIONS}
    out: list[str] = []
    for c in sorted(danger):
        g, p = gold.get(c), got.get(c)
        g_pos, p_pos = g in positive, p in positive
        if g_pos and not p_pos:
            if p == "absent":
                out.append("missed danger sign: marked absent")
            elif any(got.get(m) in positive for m in MILDER.get(c, ())):
                out.append("missed danger sign: recorded as a milder symptom")
            else:
                out.append("missed danger sign: not recorded")
        elif p_pos and not g_pos:
            if g == "absent":
                out.append("false danger sign: gold says denied")
            elif g == "historical":
                out.append("false danger sign: a past pregnancy read as current")
            elif any(gold.get(m) in positive for m in MILDER.get(c, ())):
                out.append("false danger sign: a milder symptom escalated")
            else:
                out.append("false danger sign: not said")
    s = score_item(item.item_id, item.group_id, item.gold, pred)
    if (s.bp_gold and not s.bp_exact) or (s.ga_gold and not s.ga_exact):
        out.append("measurement wrong or missing")
    for c in sorted((set(gold) | set(got)) - danger):
        g, p = gold.get(c), got.get(c)
        if g in (None, "not_mentioned") and p not in (None, "not_mentioned"):
            out.append("other finding: added")
        elif p in (None, "not_mentioned") and g not in (None, "not_mentioned"):
            out.append("other finding: missed")
        elif g != p:
            out.append("other finding: wrong assertion")
    return out


ORDER = ["invalid", "missed danger", "false danger", "measurement", "other finding"]


def primary(errors: list[str]) -> str:
    return next(e for k in ORDER for e in errors if e.startswith(k))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    danger = load_vocabulary().danger_sign_ids
    items = [it for f in SETS for it in read_jsonl(ROOT / f, BenchItem)]
    report: dict = {"sets": SETS, "seed": SEED, "sample": SAMPLE, "systems": {}}
    for name, path in SYSTEMS.items():
        preds = {p.item_id: p.record for p in read_jsonl(ROOT / path, Prediction)}
        errors = {it.item_id: item_errors(it, preds.get(it.item_id), danger) for it in items}
        wrong = sorted(i for i, e in errors.items() if e)
        sample = random.Random(SEED).sample(wrong, min(SAMPLE, len(wrong)))  # noqa: S311 (seeded)
        stratum = {it.item_id: f"{it.stratum}-{it.language}" for it in items}
        report["systems"][name] = {
            "items": len(items),
            "items_with_an_error": len(wrong),
            "all_errors": dict(Counter(e for es in errors.values() for e in es).most_common()),
            "missed_danger_by_set": dict(
                Counter(
                    stratum[i] for i, es in errors.items() for e in es if e.startswith("missed")
                ).most_common()
            ),
            "false_danger_by_set": dict(
                Counter(
                    stratum[i] for i, es in errors.items() for e in es if e.startswith("false")
                ).most_common()
            ),
            "sample_primary": dict(Counter(primary(errors[i]) for i in sample).most_common()),
            "sample_items": {i: errors[i] for i in sorted(sample)},
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, r in report["systems"].items():
        print(f"== {name}: {r['items_with_an_error']} of {r['items']} items with an error")
        print("   sample of 50, primary:", r["sample_primary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
