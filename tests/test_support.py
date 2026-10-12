"""The support check (ADR-0036): a value whose quote does not say it is flagged, never changed."""

import pytest

from phc_scribe.encounter import Encounter
from phc_scribe.support import check, has_number, mentions

# What speech recognition wrote in the end-to-end test on the laptop hub (12 Oct 2026).
E2E = (
    "mrs. adebayo 28 wk 2nd pregnancy she has had some bleeding from the vaginal scenes "
    "yesterday and a severe headache since this morning the baby moved well no fever the bps "
    "120 over 80 are i think i need to refer her to the general hospital today."
)


def _record(findings=(), vitals=None) -> Encounter:
    return Encounter.model_validate(
        {
            "schema_version": "0.1.0",
            "module": "anc",
            "findings": [
                {"concept": c, "assertion": a, "evidence": {"text": q}} for c, a, q in findings
            ],
            "vitals": vitals or {},
            "anc": {"tests": [], "medications": []},
            "disposition": {},
        }
    )


def test_the_end_to_end_draft():
    record = _record(
        [
            (
                "vaginal_bleeding",
                "present",
                "she has had some bleeding from the vaginal scenes yesterday",
            ),
            (
                "severe_headache",
                "present",
                "the baby moved well no fever the bps 120 over 80 are i think i need to refer"
                " her to the general hospital today.",
            ),
            ("reduced_fetal_movement", "present", "the baby moved well"),  # the polarity check's
        ],
        {
            "temperature": {"value": 37, "unit": "Cel", "evidence": {"text": "no fever"}},
            "blood_pressure": {
                "systolic": 120,
                "diastolic": 80,
                "evidence": {"text": "the bps 120 over 80"},
            },
        },
    )
    flags = check(record)
    assert [f.path for f in flags] == ["findings[1]", "vitals.temperature"]
    assert flags[0].detail.startswith('severe_headache is "present", but its quote does not')
    assert flags[1].detail == (
        'temperature 37 °C is in the draft, but its quote has no number: "no fever"'
    )
    assert all(q in E2E for q in ("no fever", "the bps 120 over 80"))


@pytest.mark.parametrize(
    "concept,quote",
    [
        ("vaginal_bleeding", "Ẹ̀jẹ̀ ń jáde lára mi"),
        ("vaginal_bleeding", "blood dey comot for my private part"),
        ("vaginal_bleeding", "some spotting since yesterday"),
        ("severe_headache", "orí ń fọ́ mi gan-an"),
        ("severe_headache", "my head dey pain me well well"),
        ("severe_abdominal_pain", "my belle dey pain me well well"),
        ("severe_abdominal_pain", "ikùn mi ń dùn mi gidigidi"),
        ("reduced_fetal_movement", "pikin no dey kick again"),
        ("reduced_fetal_movement", "ọmọ inú mi kò mì dáadáa"),
        ("convulsions", "mo ní gìrì lánàá"),
        ("convulsions", "she dey convulse for house"),
        ("unconscious", "complains of unresponsiveness"),
        ("unconscious", "mo dákú lánàá"),
        ("blurred_vision", "I no fit see well"),
        ("fever", "ara mi gbóná, mo ní ibà"),
        ("breathing_difficulty", "I no fit catch breath"),
        ("swelling_face_hands", "my face and hands don swell"),
        ("leaking_amniotic_fluid", "water dey comot for my private part"),
        ("severe_vomiting", "I dey vomit everything I chop"),
        ("severe_pallor", "ojú rẹ̀ jẹ́ aláwọ̀ fẹ́ẹ́fẹ́ẹ́"),
        # not checked: a general impression has no fixed words
        ("looks_very_ill", "she no look well at all"),
    ],
)
def test_real_findings_mention_their_concept(concept, quote):
    assert mentions(concept, quote)


@pytest.mark.parametrize(
    "concept,quote",
    [
        ("severe_headache", "the baby moved well no fever"),
        ("vaginal_bleeding", "TCA 4/52"),
        ("convulsions", "BP 150/100"),
        ("fever", "she is in her second pregnancy"),
    ],
)
def test_a_quote_about_something_else_is_flagged(concept, quote):
    assert not mentions(concept, quote)


@pytest.mark.parametrize(
    "quote",
    ["BP 120/80", "temp thirty seven point five", "ìwọ̀n ara rẹ̀ jẹ́ mẹ́tàdínlógójì", "wt 56kg"],
)
def test_numbers_in_digits_or_words(quote):
    assert has_number(quote)


@pytest.mark.parametrize("quote", ["no fever", "her pressure is fine", "kò sí ibà"])
def test_no_number(quote):
    assert not has_number(quote)


def test_denials_are_not_checked():
    assert check(_record([("severe_headache", "absent", "no fever")])) == []
