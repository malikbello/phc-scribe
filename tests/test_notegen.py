import random

from bench.notegen import generate, load_phrase_bank, render_note
from phc_scribe.grounding import locate
from phc_scribe.vocab import load_vocabulary


def test_phrase_bank_concepts_are_in_vocabulary():
    bank = load_phrase_bank()
    assert set(bank.forms) <= set(load_vocabulary().ids)
    assert all("{x}" in f for frames in bank.frames.values() for f in frames)


def test_generation_is_deterministic_and_verified():
    a, report = generate(40, seed=7)
    b, _ = generate(40, seed=7)
    assert [i.transcript for i in a] == [i.transcript for i in b]
    assert report.items == 40 and not report.rejected
    assert all(i.stratum == "G" and i.origin == "generated" for i in a)


def test_gold_evidence_is_verbatim_and_values_match():
    rng = random.Random(3)  # noqa: S311
    bank = load_phrase_bank()
    for _ in range(50):
        note, gold = render_note(rng, bank, want_danger=True)
        for f in gold.findings:
            assert f.evidence is not None and locate(note, f.evidence.text) is not None
        bp = gold.vitals.blood_pressure
        assert bp is not None and f"{bp.systolic}/{bp.diastolic}" in bp.evidence.text
        ga = gold.anc.gestational_age
        assert ga is not None and str(ga.weeks) in ga.evidence.text
        contact = gold.anc.contact_number
        assert contact is not None and contact.value <= max(1, (ga.weeks - 8) // 4 + 1)
