from phc_scribe.encounter import Encounter
from phc_scribe.grounding import ground, locate
from phc_scribe.text import normalise

TRANSCRIPT = normalise(
    "Ó ní ẹ̀jẹ̀ ń jáde láti àná. BP 150/100, temp 38.5. G3P2. PCV 30%. She denies convulsions."
)


def ev(text: str) -> dict:
    return {"text": text}


def test_locate_exact():
    found = locate(TRANSCRIPT, "BP 150/100")
    assert found is not None and found.level == "exact"
    assert TRANSCRIPT[found.start : found.end] == "BP 150/100"


def test_locate_without_diacritics_maps_to_original_span():
    found = locate(TRANSCRIPT, "eje n jade")
    assert found is not None and found.level == "folded"
    assert TRANSCRIPT[found.start : found.end] == normalise("ẹ̀jẹ̀ ń jáde")


def test_locate_rejects_missing_and_trivial_quotes():
    assert locate(TRANSCRIPT, "blurred vision") is None
    assert locate(TRANSCRIPT, "a") is None
    assert locate(TRANSCRIPT, "   ") is None


def test_locate_uses_hint_to_pick_occurrence():
    text = "fever yesterday; fever today"
    found = locate(text, "fever", hint=17)
    assert found is not None and found.start == 17


def test_ungrounded_finding_is_dropped_and_flagged():
    record = Encounter.model_validate(
        {
            "findings": [
                {
                    "concept": "vaginal_bleeding",
                    "assertion": "present",
                    "evidence": ev("ẹ̀jẹ̀ ń jáde"),
                },
                {
                    "concept": "blurred_vision",
                    "assertion": "present",
                    "evidence": ev("blurred vision"),
                },
            ]
        }
    )
    result = ground(record, TRANSCRIPT)
    assert [str(f.concept) for f in result.record.findings] == ["vaginal_bleeding"]
    assert result.needs_review
    assert result.ungrounded == 1
    assert result.fields_total == 2
    kept = result.record.findings[0].evidence
    assert kept is not None and kept.start is not None
    assert TRANSCRIPT[kept.start : kept.end] == kept.text


def test_invented_bp_value_is_dropped():
    record = Encounter.model_validate(
        {
            "vitals": {
                "blood_pressure": {"systolic": 160, "diastolic": 110, "evidence": ev("BP 150/100")}
            }
        }
    )
    result = ground(record, TRANSCRIPT)
    assert result.record.vitals.blood_pressure is None
    assert result.dropped[0].reason == "value_not_in_evidence"


def test_correct_values_survive():
    record = Encounter.model_validate(
        {
            "vitals": {
                "blood_pressure": {"systolic": 150, "diastolic": 100, "evidence": ev("BP 150/100")},
                "temperature": {"value": 38.5, "evidence": ev("temp 38.5")},
            },
            "anc": {
                "gravida": {"value": 3, "evidence": ev("G3P2")},
                "parity": {"value": 2, "evidence": ev("G3P2")},
                "tests": [{"test": "pcv", "value": 30, "unit": "%", "evidence": ev("PCV 30%")}],
            },
        }
    )
    result = ground(record, TRANSCRIPT)
    assert not result.needs_review, result.dropped
    assert result.record.vitals.temperature is not None
    assert result.record.anc.parity is not None


def test_inconsistent_values_are_dropped():
    text = "BP 150/100. G2 P3."
    record = Encounter.model_validate(
        {
            "vitals": {
                "blood_pressure": {"systolic": 100, "diastolic": 150, "evidence": ev("BP 150/100")}
            },
            "anc": {
                "gravida": {"value": 2, "evidence": ev("G2 P3")},
                "parity": {"value": 3, "evidence": ev("G2 P3")},
            },
        }
    )
    result = ground(record, text)
    reasons = {d.path: d.reason for d in result.dropped}
    assert reasons == {"vitals.blood_pressure": "inconsistent", "anc.parity": "inconsistent"}
    assert result.record.anc.gravida is not None


def test_out_of_range_value_is_dropped():
    text = "Weight 500 kg"
    record = Encounter.model_validate(
        {"vitals": {"weight": {"value": 500, "evidence": ev("Weight 500 kg")}}}
    )
    result = ground(record, text)
    assert result.record.vitals.weight is None
    assert result.dropped[0].reason == "out_of_range"


def test_fahrenheit_is_range_checked_in_celsius():
    text = "Temperature 101.3 F"
    record = Encounter.model_validate(
        {
            "vitals": {
                "temperature": {
                    "value": 101.3,
                    "unit": "[degF]",
                    "evidence": ev("Temperature 101.3"),
                }
            }
        }
    )
    result = ground(record, text)
    assert result.record.vitals.temperature is not None, result.dropped


def test_numbers_said_as_words_pass_the_value_check():
    text = "Her pressure is one sixty over one ten"
    record = Encounter.model_validate(
        {
            "vitals": {
                "blood_pressure": {
                    "systolic": 160,
                    "diastolic": 110,
                    "evidence": ev("one sixty over one ten"),
                }
            }
        }
    )
    assert ground(record, text).record.vitals.blood_pressure is not None
