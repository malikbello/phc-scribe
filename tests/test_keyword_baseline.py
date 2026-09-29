import pytest

from bench.baselines.keyword import extract, load_lexicon


def findings(text: str) -> set[tuple[str, str]]:
    return {(str(f.concept), str(f.assertion)) for f in extract(text).findings}


def test_lexicon_loads_and_covers_every_danger_sign():
    from phc_scribe.vocab import load_vocabulary

    assert load_vocabulary().danger_sign_ids <= set(load_lexicon().concepts)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Complains of severe headache.", {("severe_headache", "present")}),
        ("No vaginal bleeding.", {("vaginal_bleeding", "absent")}),
        ("She denies convulsions.", {("convulsions", "absent")}),
        ("Maybe fever at night.", {("fever", "possible")}),
        ("Bled in her last pregnancy.", {("vaginal_bleeding", "historical")}),
        ("Any bleeding? No.", {("vaginal_bleeding", "absent")}),
        ("Any bleeding? Yes.", {("vaginal_bleeding", "present")}),
        ("Any bleeding?", set()),
        ("No headache, fever present.", {("headache", "absent"), ("fever", "present")}),
        ("No bleeding but has cough.", {("vaginal_bleeding", "absent"), ("cough", "present")}),
        ("Kò sí ibà.", {("fever", "absent")}),
        ("Ẹ̀jẹ̀ ń jáde.", {("vaginal_bleeding", "present")}),
        ("eje n jade", {("vaginal_bleeding", "present")}),
    ],
)
def test_finding_assertions(text, expected):
    assert findings(text) == expected


def test_vitals_and_anc_shorthand():
    r = extract("G3P2+1, GA 32/40. BP 150/100, T 36.5, temp 37.2 C, wt 70kg, PR 88. PCV 29%.")
    assert r.vitals.blood_pressure is not None
    assert (r.vitals.blood_pressure.systolic, r.vitals.blood_pressure.diastolic) == (150, 100)
    assert r.vitals.temperature is not None and r.vitals.temperature.value == 37.2
    assert r.vitals.weight is not None and r.vitals.weight.value == 70
    assert r.vitals.pulse is not None and r.vitals.pulse.value == 88
    assert r.anc.gestational_age is not None and r.anc.gestational_age.weeks == 32
    assert r.anc.gravida is not None and r.anc.gravida.value == 3
    assert r.anc.parity is not None and r.anc.parity.value == 2
    assert [(str(t.test), t.value) for t in r.anc.tests] == [("pcv", 29.0)]


def test_dates_and_ga_are_not_read_as_bp():
    r = extract("Seen 29/09/2026 at 32/40, return in 2/52.")
    assert r.vitals.blood_pressure is None


def test_negated_medication_is_skipped():
    r = extract("Given fefol. No SP today.")
    assert [str(m.medication) for m in r.anc.medications] == ["iron_folic_acid"]


def test_referral_and_next_visit():
    r = extract("Referred to Adeoyo Maternity Hospital. TCA in 2/52.")
    assert r.disposition.referral is not None
    assert r.disposition.referral.referred
    assert r.disposition.referral.destination == "Adeoyo Maternity Hospital"
    assert r.disposition.next_visit is not None
    assert r.disposition.next_visit.text == "TCA in 2/52"


def test_every_evidence_span_points_into_the_transcript():
    text = "Ó ní orí ń fọ́ òun gidigidi. BP 160/110. Kò sí ẹ̀jẹ̀ ń jáde. Referred to UCH."
    r = extract(text)
    spans = [f.evidence for f in r.findings]
    spans += [r.vitals.blood_pressure.evidence] if r.vitals.blood_pressure else []
    for e in spans:
        assert e is not None and e.start is not None
        assert text[e.start : e.end] == e.text
