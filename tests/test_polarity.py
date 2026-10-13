"""The polarity check (ADR-0030): narrow cues, flag only; a danger sign said with a negator kept."""

import pytest

from phc_scribe.polarity import reads_opposite


@pytest.mark.parametrize(
    "concept,quote,cue",
    [
        ("reduced_fetal_movement", "the baby moves well", "normal_state"),
        (
            "reduced_fetal_movement",
            "is the baby moving well? yes, the baby moves well",
            "normal_state",
        ),
        ("reduced_fetal_movement", "Ọmọ inú mi ń mì dáadáa", "normal_state"),
        ("reduced_fetal_movement", "pikin dey kick well well", "normal_state"),
        # past tense, as speech recognition wrote "moves well" in the 11 Oct hub test
        ("reduced_fetal_movement", "the baby moved well", "normal_state"),
        ("reduced_fetal_movement", "the baby kicked well this morning", "normal_state"),
        ("unconscious", "she is conscious and alert", "normal_state"),
        ("unconscious", "denies unresponsiveness", "denial"),
        ("vaginal_bleeding", "No bleeding", "denial"),
        ("vaginal_bleeding", "Any bleeding? No.", "denial"),
        ("severe_headache", "denies headache", "denial"),
        ("convulsions", "fits: nil", "denial"),
        ("fever", "Kò sí ibà", "denial"),
        ("leg_oedema", "denies pain on passing urine; swollen ankles: nil.", "denial"),
    ],
)
def test_flags_a_quote_that_says_the_opposite(concept, quote, cue):
    assert reads_opposite(concept, "present", quote) == cue


@pytest.mark.parametrize(
    "concept,quote",
    [
        # danger signs said with a negator are present: never flagged
        ("reduced_fetal_movement", "Pikin for my belle no dey move like before"),
        ("reduced_fetal_movement", "Ọmọ inú mi kò mì dáadáa bí ti tẹ́lẹ̀ mọ́"),
        ("reduced_fetal_movement", "the baby is not moving well"),
        ("reduced_fetal_movement", "baby hasn't kicked since yesterday"),
        ("reduced_fetal_movement", "the baby has not moved well since yesterday"),
        ("reduced_fetal_movement", "the baby moved less today"),
        ("unconscious", "she no dey respond"),
        ("unconscious", "she is unconscious"),
        ("blurred_vision", "I no fit see well"),
        ("blurred_vision", "I cannot see clearly"),
        # a denial of something else in the same quote does not count
        (
            "vaginal_bleeding",
            "presented with bleeding per vaginam; denies gush of fluid per vaginam;",
        ),
        ("vaginal_bleeding", "Any bleeding? No, but there is some spotting"),
        ("severe_headache", "severe headache, not relieved by paracetamol"),
    ],
)
def test_leaves_real_findings_alone(concept, quote):
    assert reads_opposite(concept, "present", quote) is None


def test_absent_findings_are_not_judged():
    assert reads_opposite("vaginal_bleeding", "absent", "No bleeding") is None
    assert reads_opposite("reduced_fetal_movement", "absent", "the baby moves well") is None


def test_possible_and_historical_are_judged_too():
    assert reads_opposite("convulsions", "possible", "fits: nil") == "denial"
    assert reads_opposite("convulsions", "historical", "never had fits") == "denial"


# Speech recognition writes no punctuation, so one clause can hold the whole visit.
@pytest.mark.parametrize(
    "quote",
    [
        # the 13 Oct sandbox test: "no fever" came out as "not feverar"
        "the baby moved well not feverar the bpe is 120 by 80 i think i need to refer her",
        "the baby moves well in love with her the bp is 120 by 80",
        "pikin dey kick well well she no get fever",
    ],
)
def test_flags_normal_movement_in_unpunctuated_speech(quote):
    assert reads_opposite("reduced_fetal_movement", "present", quote) == "normal_state"


@pytest.mark.parametrize(
    "quote",
    [
        "the baby was moving well before but now she is not moving",
        "she said the baby moved well yesterday but today the baby moves less",
        "the baby moved well last week today it has not kicked at all",
        "baby dey move small small since morning she no get fever",
        "omo inu mi n mi daadaa tele sugbon lonii ko mi rara",
    ],
)
def test_keeps_reduced_movement_said_anywhere_in_the_quote(quote):
    assert reads_opposite("reduced_fetal_movement", "present", quote) is None
