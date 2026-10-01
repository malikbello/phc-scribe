import pytest

from phc_scribe.rules import Facts
from phc_scribe.visit_guide import (
    GUIDE_PATH,
    LEXICON_PATH,
    item_ids,
    load_guide,
    load_raw,
    parse_guide,
)


def test_guide_loads_and_every_item_can_be_covered():
    g = load_guide()
    assert len(g.items) >= 25 and g.follow_ups
    assert {i.group for i in g.items} <= set(g.groups)


def test_negated_answers_still_cover_the_question():
    g = load_guide()
    st = g.status(
        "Any bleeding? No bleeding. No headache, no fever.", first_contact=False, weeks=30
    )
    covered = item_ids(st["items"], True)
    assert {"ask-bleeding", "ask-headache-vision", "ask-fever"} <= set(covered)
    assert "check-bp" not in covered


def test_yoruba_and_pidgin_forms_count_and_tone_marks_do_not_matter():
    g = load_guide()
    st = g.status("ori n fo mi, pikin dey move well", weeks=24)  # no tone marks
    covered = set(item_ids(st["items"], True))
    assert {"ask-headache-vision", "ask-movement"} <= covered


def test_due_rules_never_hide_items_when_unknown():
    g = load_guide()
    ids_unknown = {i["id"] for i in g.status("")["items"]}
    ids_later = {i["id"] for i in g.status("", first_contact=False, weeks=10)["items"]}
    assert {"ask-lmp", "ask-movement", "plan-birth"} <= ids_unknown
    assert not {"ask-lmp", "ask-movement", "plan-birth"} & ids_later


def test_follow_ups_fire_on_findings_and_only_list_open_asks():
    g = load_guide()
    facts = Facts.from_dict({"findings": {"headache": ["present"]}, "vitals": {"bp_systolic": 150}})
    st = g.status("she has headache", facts=facts, weeks=30)
    fu = {f["id"]: f["ask"] for f in st["follow_ups"]}
    assert "fu-headache" not in fu  # both asks already covered: nothing to prompt
    facts = Facts.from_dict({"findings": {"fever": ["present"]}})
    st = g.status("hot body since yesterday", facts=facts)
    assert {"id": "fu-fever", "ask": ["check-temperature", "test-malaria"]} in st["follow_ups"]
    absent = Facts.from_dict({"findings": {"fever": ["absent"]}})
    assert not g.status("no fever", facts=absent)["follow_ups"]


def test_bad_content_fails_loudly():
    raw, lex = load_raw(GUIDE_PATH), load_raw(LEXICON_PATH)
    raw["items"][0]["covered_by"] = {"concepts": ["not_a_concept"]}
    with pytest.raises(ValueError, match="unknown concept"):
        parse_guide(raw, lex)
    raw, lex = load_raw(GUIDE_PATH), load_raw(LEXICON_PATH)
    raw["follow_ups"][0]["ask"] = ["no-such-item"]
    with pytest.raises(ValueError, match="unknown item"):
        parse_guide(raw, lex)
