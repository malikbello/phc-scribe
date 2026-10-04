from bench.synth import compose, parse_class, rule_check, spec


def _row(lang, concept, assertion):
    return {"language": lang, "concept": concept, "assertion": assertion}


def test_rule_check_accepts_well_formed_sentences():
    ok = [
        (_row("yo", "vaginal_bleeding", "absent"), "Kò sí ẹ̀jẹ̀ kankan tó ń jáde lójú ara mi"),
        (_row("yo", "fever", "possible"), "Bóyá ibà ló ń ṣe mí lálẹ́"),
        (_row("yo", "convulsions", "historical"), "Gìrì mú mi nígbà oyún àkọ́kọ́ mi"),
        (_row("pcm", "severe_headache", "present"), "My head dey pain me die since morning"),
        (_row("pcm", "headache", "present"), "My head dey pain me small"),
        (_row("en", "reduced_fetal_movement", "present"), "My baby moves much less than before"),
        (_row("yo", None, None), "Ó dára kí aboyún máa jẹ ẹ̀fọ́"),
    ]
    for row, text in ok:
        assert rule_check(row, text) is None, (row, text)


def test_rule_check_rejects_wrong_cue_language_or_severity():
    assert rule_check(_row("pcm", "fever", "absent"), "My body dey hot") == "no_absent_cue"
    assert rule_check(_row("yo", "fever", "present"), "My body is hot") == "not_yoruba"
    assert rule_check(_row("pcm", "severe_headache", "present"), "My head dey pain me") == (
        "no_severity_cue"
    )
    denied = rule_check(_row("en", "fever", "present"), "I don't have fever")
    assert denied == "present_has_absent_cue"


def test_parse_class_and_spec():
    assert parse_class(" Absent.") == "absent" and parse_class("I think: possible") == "possible"
    assert parse_class("maybe yes") == "unparsed"
    rows = spec()
    assert len(rows) == len({r["id"] for r in rows})
    assert {r["language"] for r in rows} == {"yo", "pcm", "en"}


def test_compose_uses_each_sentence_once_and_keeps_gold_exact():
    rows = [
        {**_row("pcm", "fever", "present"), "text": "My body dey hot.", "kept": True},
        {**_row("pcm", "headache", "present"), "text": "My head dey pain me small.", "kept": True},
        {
            **_row("pcm", "severe_headache", "present"),
            "text": "My head dey bang me die.",
            "kept": True,
        },
        {**_row("pcm", None, None), "text": "Make pregnant woman rest well.", "kept": True},
    ]
    items = compose(rows, seed=3)
    texts = " ".join(i.transcript for i in items)
    for r in rows:
        assert texts.count(r["text"]) == 1
    for i in items:
        concepts = {str(f.concept) for f in i.gold.findings}
        assert not {"headache", "severe_headache"} <= concepts
        assert all(f.evidence and f.evidence.text in i.transcript for f in i.gold.findings)
