import json

from phc_scribe.encounter import Encounter
from phc_scribe.salvage import salvage

EV = {"text": "BP 135/73"}


def record(**anc) -> dict:
    return {
        "findings": [
            {"concept": "dizziness", "assertion": "present", "evidence": {"text": "dizzy"}}
        ],
        "anc": anc,
    }


def test_a_test_without_a_result_is_removed_and_reported():
    data = record(
        tests=[
            {"test": "urine_protein", "evidence": {"text": "TCA 2/52"}},
            {"test": "urine_protein", "result": "negative", "evidence": {"text": "protein neg"}},
        ]
    )
    rec, repairs = salvage(data)
    assert rec is not None and len(rec.anc.tests) == 1
    assert [r.path for r in repairs] == ["anc.tests[0]"]
    assert data["anc"]["tests"][0].get("result") is None  # the input is not mutated


def test_an_unnamed_other_medication_is_removed():
    rec, repairs = salvage(
        record(medications=[{"medication": "other", "evidence": {"text": "given drugs"}}])
    )
    assert rec is not None and rec.anc.medications == []
    assert [r.path for r in repairs] == ["anc.medications[0]"]


def test_a_repeated_finding_keeps_the_first():
    data = record()
    data["findings"].append(
        {"concept": "dizziness", "assertion": "present", "evidence": {"text": "dizzy spells"}}
    )
    rec, repairs = salvage(data)
    assert rec is not None and len(rec.findings) == 1
    ev = rec.findings[0].evidence
    assert ev is not None and ev.text == "dizzy"
    assert repairs[0].path == "findings[1]"


def test_nothing_else_is_repaired():
    # value without unit is a different violation: salvage must not guess a unit
    data = record(tests=[{"test": "hb", "value": 9.0, "evidence": {"text": "Hb 9"}}])
    assert salvage(data) == (None, [])
    assert salvage("not a record") == (None, [])
    assert salvage(None) == (None, [])


def test_a_valid_record_is_not_touched():
    data = record(tests=[{"test": "urine_protein", "result": "1+", "evidence": EV}])
    Encounter.model_validate(data)
    assert salvage(json.loads(json.dumps(data))) == (None, [])
