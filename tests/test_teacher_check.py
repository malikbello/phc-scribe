import sys
from pathlib import Path

from bench.label_queue import Label
from bench.teacher import to_items
from phc_scribe.encounter import Encounter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from teacher_check import sample, score, to_queue

from tests.test_teacher import _rows


def _with(item, concept=None, assertion="present"):
    if concept is None:
        return item
    gold = Encounter.model_validate(
        {"findings": [{"concept": concept, "assertion": assertion, "evidence": {"text": "belle"}}]}
    )
    return item.model_copy(update={"gold": gold})


def test_sample_is_seeded_and_balanced():
    kept = to_items(_rows(80, "yo") + _rows(80, "pcm"), per_language=60, enriched_share=0.5)
    a, b = sample(kept), sample(list(reversed(kept)))
    assert [i.item_id for i in a] == [i.item_id for i in b]
    assert len(a) == 50 and sum(i.language == "yo" for i in a) == 25
    q = to_queue(a)
    assert all(x.item_id.startswith("tc-") and not x.hints for x in q)  # blind: no hints


def test_score_counts_danger_errors_and_applies_the_one_in_five_rule():
    kept = to_items(_rows(10), per_language=4, enriched_share=0.5)
    kept = [_with(kept[0], "vaginal_bleeding"), _with(kept[1], "cough"), kept[2], kept[3]]

    def lab(i, concept=None, status="labelled"):
        findings = (
            []
            if concept is None
            else [{"concept": concept, "assertion": "present", "evidence": {"text": "belle"}}]
        )
        return Label.model_validate(
            {
                "item_id": f"tc-{kept[i].item_id}",
                "status": status,
                "findings": findings,
                "labeller": "admin",
                "labelled_at": "2026-10-02T10:00:00Z",
            }
        )

    # item 0: checker missed the danger sign; item 1: non-danger difference; 2: match; 3: skip
    r = score(kept, [lab(0), lab(1), lab(2), lab(3, status="skip")])
    assert r["checked"] == 3 and r["unlabellable"] == 1
    assert r["danger_errors"] == 1 and r["full_matches"] == 1
    assert r["use_teacher_labels"] is False  # 1/3 > 1/5
