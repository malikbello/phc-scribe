"""Metric definitions plus the smoke-eval: the whole harness over constructed items."""

import json
from pathlib import Path

from bench.baselines import keyword
from bench.harness import main, report, run_system, score
from bench.items import BenchItem, Prediction, read_jsonl
from bench.metrics import score_item
from phc_scribe.encounter import Encounter

SMOKE = Path(__file__).parent / "fixtures" / "smoke_items.jsonl"


def rec(findings: list[tuple[str, str]], bp: tuple[int, int] | None = None) -> Encounter:
    data: dict = {
        "findings": [
            {"concept": c, "assertion": a, "evidence": {"text": "quote"}} for c, a in findings
        ]
    }
    if bp:
        data["vitals"] = {
            "blood_pressure": {"systolic": bp[0], "diastolic": bp[1], "evidence": {"text": "bp"}}
        }
    return Encounter.model_validate(data)


def test_possible_counts_as_positive_and_historical_does_not():
    gold = rec([("vaginal_bleeding", "present"), ("convulsions", "historical")])
    pred = rec([("vaginal_bleeding", "possible"), ("convulsions", "historical")])
    s = score_item("i", "g", gold, pred)
    assert (s.danger_tp, s.danger_fn, s.danger_fp) == (1, 0, 0)
    # the assertion differs, so the (concept, assertion) pair is still wrong
    assert (s.pair_tp, s.pair_fp, s.pair_fn) == (1, 1, 1)


def test_schema_invalid_prediction_misses_everything():
    gold = rec([("fever", "present")], bp=(120, 80))
    s = score_item("i", "g", gold, None)
    assert not s.schema_valid
    assert (s.danger_tp, s.danger_fn) == (0, 1)
    assert s.bp_gold and not s.bp_exact


def test_false_alarm_only_counts_on_items_without_danger():
    s = score_item("i", "g", rec([("headache", "present")]), rec([("fever", "present")]))
    assert not s.gold_has_danger and s.pred_has_danger


def test_rule_flags_compared_end_to_end():
    gold = rec([], bp=(165, 100))
    s = score_item("i", "g", gold, rec([], bp=(165, 100)))
    assert (s.flags_gold, s.flags_hit) == (1, 1)


def test_smoke_eval_keyword_baseline(tmp_path):
    items = list(read_jsonl(SMOKE, BenchItem))
    assert items and all(i.origin == "constructed" for i in items)
    preds = run_system(keyword.SYSTEM_NAME, keyword.extract, items)
    assert all(p.error is None for p in preds)
    scores = score(items, preds)
    assert all(s.schema_valid for s in scores)
    assert all(s.fields_ungrounded == 0 for s in scores)  # the baseline quotes the transcript
    out = report(items, preds, baseline=preds)
    assert out["vs_baseline"]["diff"]["danger_recall"]["point"] == 0  # type: ignore[index]


def test_cli_run_then_score(tmp_path):
    preds_path = tmp_path / "preds.jsonl"
    report_path = tmp_path / "report.json"
    assert (
        main(["run", "--system", "keyword", "--items", str(SMOKE), "--out", str(preds_path)]) == 0
    )
    assert (
        main(["score", "--items", str(SMOKE), "--pred", str(preds_path), "--out", str(report_path)])
        == 0
    )
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(data["by_language"]) == {"en", "yo"}
    assert 0 <= data["overall"]["danger_recall"]["point"] <= 1
    assert list(read_jsonl(preds_path, Prediction))
