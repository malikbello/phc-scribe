import pytest

from bench.data_audit import (
    AuditCounts,
    card_topics,
    has_danger_keyword,
    language_guess,
    primary_visit_type,
    visit_types,
)
from phc_scribe.deid import find_identifiers, scrub


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Call husband on 0803 123 4567 today", "phone"),
        ("Phone +2348031234567", "phone"),
        ("email ada.o@example.com", "email"),
        ("Seen on 12/03/2026", "date"),
        ("Seen on 3rd March 2026", "date"),
        ("Hosp No: UCH/23/4455", "record_number"),
        ("Name: Adunni Bello", "labelled_name"),
        ("Lives at 14 Adeola Odeku Street", "address"),
    ],
)
def test_identifier_kinds(text, kind):
    assert kind in {h.kind for h in find_identifiers(text)}


def test_clinical_numbers_are_not_identifiers():
    text = "BP 120/80, GA 32/40, G3P2, PCV 30%, temp 37.2, TCA 2/52"
    assert find_identifiers(text) == []


def test_scrub_replaces_identifiers_and_keeps_clinical_text():
    out = scrub("Name: Adunni Bello, 08031234567. BP 150/100.")
    assert "Adunni" not in out and "08031234567" not in out
    assert "[LABELLED_NAME]" in out and "[PHONE]" in out
    assert "BP 150/100." in out


def test_visit_type_heuristics():
    anc = "ANC booking. G2P1, GA 16/40, fundal height 16 cm."
    assert primary_visit_type(anc) == "anc"
    assert "anc" in visit_types(anc)
    assert primary_visit_type("C/o fever for 3 days. Impression: malaria. Rx ACT.") == "general_opd"
    assert primary_visit_type("Nothing clinical here") == "unknown"


def test_language_guess():
    assert language_guess("She complains of headache and fever since yesterday.") == "en"
    assert language_guess("Ó ní orí ń fọ́ òun, ẹsẹ̀ rẹ̀ sì wú.") == "yo"
    assert language_guess("Abeg wetin dey worry the pikin?") == "pcm"


def test_danger_keyword_detection():
    assert has_danger_keyword("Complains of vaginal bleeding")
    assert not has_danger_keyword("Mild back pain")


def test_audit_counts_are_aggregates_only():
    counts = AuditCounts().add_all(
        [
            "ANC visit, GA 30/40, BP 150/100, severe headache. Name: Adunni Bello",
            "ANC visit, GA 30/40, BP 150/100, severe headache. Name: Adunni Bello",
            "",
            "C/o cough. Impression: URTI.",
        ]
    )
    s = counts.summary()
    assert s["rows"] == 4 and s["empty_text"] == 1 and s["exact_duplicates"] == 1
    assert s["visit_type_primary"] == {"anc": 2, "general_opd": 1}
    assert s["rows_with_bp"] == 2 and s["rows_with_ga"] == 2
    assert s["anc_rows_with_danger_keyword"] == 2
    assert s["rows_with_identifier"] == {"labelled_name": 2}
    assert "Adunni" not in repr(s)


def test_card_topics():
    card = "License: CC BY 4.0. Consent was obtained. Records were anonymised."
    topics = card_topics(card)
    assert topics["license"] >= 1 and topics["consent"] == 1 and topics["deidentification"] == 1
    assert topics["ethics"] == 0
