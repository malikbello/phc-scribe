import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from phc_scribe.encounter import Encounter, decoding_schema, dumps_json_schema
from phc_scribe.vocab import load_vocabulary

ROOT = Path(__file__).resolve().parents[1]


def ev(text: str) -> dict:
    return {"text": text}


def test_committed_json_schema_matches_models():
    committed = (ROOT / "schema" / "encounter.v0.1.json").read_text(encoding="utf-8")
    assert committed == dumps_json_schema(), "run: python scripts/export_schema.py"


def test_schema_concept_enum_is_the_vocabulary():
    schema = json.loads(dumps_json_schema())
    assert schema["$defs"]["ConceptId"]["enum"] == list(load_vocabulary().ids)


def test_decoding_schema_has_no_offsets():
    evidence = decoding_schema()["$defs"]["Evidence"]
    assert set(evidence["properties"]) == {"text"}


def test_decoding_schema_bounds_generated_lists_but_published_schema_does_not():
    # ADR-0024: a loop that repeats an item cannot run to the token cap
    dec = decoding_schema()
    assert dec["properties"]["findings"]["maxItems"] == 10
    assert dec["$defs"]["Anc"]["properties"]["tests"]["maxItems"] == 10
    assert dec["$defs"]["Anc"]["properties"]["medications"]["maxItems"] == 10
    published = json.loads(dumps_json_schema())
    assert "maxItems" not in published["properties"]["findings"]


def test_list_bound_is_above_every_real_gold_record():
    # the bound must never cut a genuine record (largest real record: 5 findings)
    for path in (ROOT / "data" / "bench").glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            gold = json.loads(line).get("gold") or {}
            assert len(gold.get("findings", [])) <= 10, path.name


def test_vocabulary_has_danger_signs():
    vocab = load_vocabulary()
    assert "vaginal_bleeding" in vocab.danger_sign_ids
    assert "headache" not in vocab.danger_sign_ids


def test_minimal_record_is_valid():
    record = Encounter.model_validate({})
    assert record.schema_version == "0.1.0"
    assert record.findings == []


def test_finding_needs_evidence():
    with pytest.raises(ValidationError):
        Encounter.model_validate({"findings": [{"concept": "fever", "assertion": "present"}]})


def test_not_mentioned_needs_no_evidence():
    Encounter.model_validate({"findings": [{"concept": "fever", "assertion": "not_mentioned"}]})


def test_unknown_concept_rejected():
    with pytest.raises(ValidationError):
        Encounter.model_validate(
            {"findings": [{"concept": "headache_ish", "assertion": "present", "evidence": ev("x")}]}
        )


def test_duplicate_finding_rejected_but_two_assertions_allowed():
    bled_before = {"concept": "vaginal_bleeding", "assertion": "historical", "evidence": ev("bled")}
    none_now = {"concept": "vaginal_bleeding", "assertion": "absent", "evidence": ev("no bleeding")}
    Encounter.model_validate({"findings": [bled_before, none_now]})
    with pytest.raises(ValidationError):
        Encounter.model_validate({"findings": [bled_before, bled_before]})


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        Encounter.model_validate({"diagnosis": "pre-eclampsia"})


def test_test_result_needs_a_result_or_value():
    with pytest.raises(ValidationError):
        Encounter.model_validate({"anc": {"tests": [{"test": "pcv", "evidence": ev("PCV")}]}})


def test_value_and_unit_go_together():
    with pytest.raises(ValidationError):
        Encounter.model_validate(
            {"anc": {"tests": [{"test": "pcv", "value": 30, "evidence": ev("PCV 30")}]}}
        )


def test_other_medication_needs_a_name():
    with pytest.raises(ValidationError):
        Encounter.model_validate(
            {"anc": {"medications": [{"medication": "other", "evidence": ev("some drug")}]}}
        )


def test_evidence_offsets_come_in_pairs():
    with pytest.raises(ValidationError):
        Encounter.model_validate(
            {
                "findings": [
                    {
                        "concept": "fever",
                        "assertion": "present",
                        "evidence": {"text": "fever", "start": 3},
                    }
                ]
            }
        )
