from bench.committee import DOUBLE_SHARE, SAMPLE, majority_record, stratum_of, triage_items, vote
from bench.items import BenchItem, Prediction
from phc_scribe.encounter import Encounter
from phc_scribe.vocab import load_vocabulary

DANGER = load_vocabulary().danger_sign_ids
TEXT = "my belle dey pain me small and I get fever since yesterday"


def _rec(*findings: tuple[str, str, str], bp: tuple[int, int] | None = None) -> Encounter:
    data: dict = {
        "findings": [
            {"concept": c, "assertion": a, "evidence": {"text": q}} for c, a, q in findings
        ]
    }
    if bp:
        data["vitals"] = {
            "blood_pressure": {"systolic": bp[0], "diastolic": bp[1], "evidence": {"text": "x"}}
        }
    return Encounter.model_validate(data)


def _pred(item_id: str, rec: Encounter | None, system: str = "m") -> Prediction:
    return Prediction(item_id=item_id, system=system, record=rec, error=None if rec else "bad")


PAIN = ("abdominal_pain", "present", "belle dey pain me")
FEVER = ("fever", "present", "fever")


def test_consensus_without_danger_is_stratum_b():
    votes = [vote(_pred("i", _rec(PAIN)), TEXT, DANGER) for _ in range(3)]
    assert stratum_of(votes) == ("B", [])


def test_danger_disagreement_invalid_and_ungrounded_go_to_a():
    pain = vote(_pred("i", _rec(PAIN)), TEXT, DANGER)
    fever = vote(_pred("i", _rec(PAIN, FEVER)), TEXT, DANGER)
    invalid = vote(_pred("i", None), TEXT, DANGER)
    made_up = vote(_pred("i", _rec(("abdominal_pain", "present", "not said"))), TEXT, DANGER)
    assert stratum_of([fever, fever, fever]) == ("A", ["danger"])
    assert stratum_of([pain, pain, invalid]) == ("A", ["invalid"])
    assert stratum_of([pain, pain, made_up])[1][0] == "ungrounded"
    absent = vote(_pred("i", _rec(("abdominal_pain", "absent", "belle"))), TEXT, DANGER)
    assert stratum_of([pain, pain, absent]) == ("A", ["disagree"])


def test_majority_keeps_what_two_of_three_say():
    gold = majority_record([_rec(PAIN, bp=(120, 80)), _rec(PAIN, FEVER), _rec(bp=(120, 80))])
    assert [(str(f.concept), str(f.assertion)) for f in gold.findings] == [
        ("abdominal_pain", "present")
    ]
    bp = gold.vitals.blood_pressure
    assert bp is not None and (bp.systolic, bp.diastolic) == (120, 80)


def test_triage_samples_within_strata_and_is_seeded():
    items = [
        BenchItem(
            item_id=f"s4w-pcm-{i:03d}",
            group_id=f"wazobia:S{i % 5}",
            stratum="S4W",
            language="pcm",
            origin="real",
            transcript=TEXT,
            gold=Encounter(),
        )
        for i in range(300)
    ]
    # Items 0-149: all agree on pain (B). 150-299: one member adds fever (danger, A).
    preds = {
        m: {
            it.item_id: _pred(
                it.item_id, _rec(PAIN, FEVER) if m == "c" and n >= 150 else _rec(PAIN)
            )
            for n, it in enumerate(items)
        }
        for m in ("a", "b", "c")
    }
    gold, triage, report = triage_items(items, preds, seed=7)
    assert (report.stratum_a, report.stratum_b) == (150, 150)
    assert (report.sampled_a, report.sampled_b) == (SAMPLE["A"], SAMPLE["B"])
    assert report.double_labelled == round((SAMPLE["A"] + SAMPLE["B"]) * DOUBLE_SHARE)
    assert report.gold_with_danger == 0  # fever was one member's view only
    assert all(g.gold.findings for g in gold)
    _, again, _ = triage_items(items, preds, seed=7)
    assert [t.sampled for t in triage] == [t.sampled for t in again]
