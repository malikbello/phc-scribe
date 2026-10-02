from pathlib import Path

import pytest

from bench.items import BenchItem
from bench.train_data import (
    PhrasebankError,
    audit_teacher,
    cap_share,
    concept_precision,
    concepts_to_drop,
    drop_items_with,
    load_phrasebank,
    split_by_group,
)
from phc_scribe.encounter import Encounter


def item(
    i: str, findings: list[tuple[str, str, str]], group: str | None = None, text: str = ""
) -> BenchItem:
    text = text or " ".join(q for _, _, q in findings) or f"general talk {i}"
    record = Encounter.model_validate(
        {
            "findings": [
                {"concept": c, "assertion": a, "evidence": {"text": q}} for c, a, q in findings
            ]
        }
    )
    return BenchItem(
        item_id=i,
        group_id=group or f"g-{i}",
        stratum="T",
        language="pcm",
        origin="real",
        transcript=text,
        gold=record,
    )


def test_audit_removes_health_worker_only_concept_and_keeps_the_rest():
    items = [
        item("a", [("looks_very_ill", "present", "she dey sick")]),
        item("b", [("looks_very_ill", "present", "na sick"), ("fever", "present", "body dey hot")]),
        item("c", [("vaginal_bleeding", "present", "blood dey comot")]),
    ]
    out, rep = audit_teacher(items, empty_cap=1.0)
    by_id = {i.item_id: i for i in out}
    assert rep.findings_removed == 2 and rep.items_changed == 2 and rep.became_empty == 1
    assert [str(f.concept) for f in by_id["b"].gold.findings] == ["fever"]
    assert by_id["a"].gold.findings == []  # the only finding was impossible from this speaker
    assert [str(f.concept) for f in by_id["c"].gold.findings] == ["vaginal_bleeding"]


def test_audit_reapplies_the_empty_cap():
    full = [item(f"f{n}", [("fever", "present", f"hot {n}")]) for n in range(2)]
    empty = [item(f"e{n}", []) for n in range(5)]
    out, rep = audit_teacher(full + empty, empty_cap=0.5)
    assert sum(1 for i in out if not i.gold.findings) == 2  # at most half of the kept set
    assert rep.empty_over_cap == 3 and rep.kept == 4


def test_concept_precision_and_drop_rule():
    teacher = [
        item(f"t{n}", [("vaginal_bleeding", "present", f"blood {n}")]).gold for n in range(4)
    ]
    human = [{"vaginal_bleeding"}, set(), set(), {"vaginal_bleeding"}]  # 2 of 4 confirmed
    teacher.append(item("x", [("fever", "present", "hot")]).gold)
    human.append(set())  # 0 of 1: too little evidence to judge
    prec = concept_precision(zip(teacher, human, strict=True))
    assert prec["vaginal_bleeding"]["precision"] == 0.5
    assert concepts_to_drop(prec, floor=0.8, min_support=3) == ["vaginal_bleeding"]


def test_drop_items_with_removes_whole_items_not_findings():
    items = [
        item("a", [("fever", "present", "hot")]),
        item("b", [("headache", "present", "head dey pain")]),
    ]
    assert [i.item_id for i in drop_items_with(items, ["fever"])] == ["b"]


def test_split_by_group_keeps_groups_whole_and_is_stable():
    items = [item(f"i{n}", [], group=f"spk{n % 40}") for n in range(400)]
    train, dev = split_by_group(items, dev_frac=0.15, seed=1)
    assert not {i.group_id for i in train} & {i.group_id for i in dev}
    assert 0.05 < len(dev) / len(items) < 0.3
    _, dev2 = split_by_group(items[:200], dev_frac=0.15, seed=1)
    assert {i.group_id for i in dev2} <= {
        i.group_id for i in dev
    }  # adding items never moves a group


def test_phrasebank_refused_until_both_approvals(tmp_path: Path):
    p = tmp_path / "pb.yaml"
    p.write_text(
        "approved_by: {language: null, clinical: Rahmat}\n"
        "entries:\n"
        "  - {id: rfm-pcm-01, language: pcm, concept: reduced_fetal_movement, assertion: present,\n"
        "     text: 'Pikin for my belle no dey move like before',\n"
        "     evidence: 'Pikin for my belle no dey move'}\n",
        encoding="utf-8",
    )
    with pytest.raises(PhrasebankError, match="language"):
        load_phrasebank(p)
    p.write_text(
        p.read_text(encoding="utf-8").replace("language: null", "language: Malik"), encoding="utf-8"
    )
    [it] = load_phrasebank(p)
    assert it.stratum == "P" and it.origin == "constructed"
    assert str(it.gold.findings[0].concept) == "reduced_fetal_movement"


def test_phrasebank_rejects_evidence_not_in_text(tmp_path: Path):
    p = tmp_path / "pb.yaml"
    p.write_text(
        "approved_by: {language: Malik, clinical: Rahmat}\n"
        "entries:\n"
        "  - {id: x, language: pcm, concept: convulsions, assertion: present,\n"
        "     text: 'She dey shake', evidence: 'she get fit'}\n",
        encoding="utf-8",
    )
    with pytest.raises(PhrasebankError, match="verbatim"):
        load_phrasebank(p)


def test_cap_share_limits_constructed_items():
    main = [item(f"m{n}", []) for n in range(85)]
    extra = [item(f"x{n}", []) for n in range(40)]
    assert len(cap_share(main, extra, 0.15)) == 15  # 15 / (85 + 15) = 15%
