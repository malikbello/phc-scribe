import json
from pathlib import Path

import pytest

from bench.items import BenchItem, Prediction, read_jsonl
from bench.metrics import danger_positives
from phc_scribe.vocab import load_vocabulary
from scripts.ppi_score import SAFETY_EXIT, InputError, main, run

FIXTURE = Path(__file__).parent / "fixtures" / "smoke_items.jsonl"
DANGER = load_vocabulary().danger_sign_ids


def _world(n_copies: int = 6):
    """Copies of the smoke items as S4-W-like items: alternate strata A/B, one speaker per
    pair of items, so the cluster bootstrap has several groups per stratum."""
    base = list(read_jsonl(FIXTURE, BenchItem))
    items, triage = [], {}
    for c in range(n_copies):
        for k, it in enumerate(base):
            iid = f"{it.item_id}-c{c}"
            items.append(it.model_copy(update={"item_id": iid, "group_id": f"spk{c}-{k // 2}"}))
            triage[iid] = {"item_id": iid, "stratum": "A" if k % 2 == 0 else "B", "sampled": False}
    return items, triage


def _without_danger(item: BenchItem) -> BenchItem:
    kept = [f for f in item.gold.findings if f.concept not in DANGER]
    return item.model_copy(update={"gold": item.gold.model_copy(update={"findings": kept})})


def _preds(items, name, *, perfect: bool):
    return [
        Prediction(item_id=i.item_id, system=name, record=i.gold if perfect else None)
        for i in items
    ]


def _sample(triage, items, every: int = 2):
    chosen = [i for n, i in enumerate(items) if n % every == 0]
    for i in chosen:
        triage[i.item_id]["sampled"] = True
    return chosen


def test_perfect_system_and_paired_difference():
    items, triage = _world()
    human = _sample(triage, items)
    systems = {
        "perfect": _preds(items, "perfect", perfect=True),
        "empty": _preds(items, "empty", perfect=False),
    }
    out = run(items, human, triage, systems, [("perfect", "empty")], n_resamples=200)
    assert not out["safety_stop"]["triggered"]
    p = out["systems"]["perfect"]
    assert p["danger_recall"]["ppi"]["point"] == pytest.approx(1.0)
    assert p["false_alarm_rate"]["ppi"]["point"] == pytest.approx(0.0)
    assert out["systems"]["empty"]["schema_valid_rate"]["ppi"]["point"] == pytest.approx(0.0)
    diff = out["pairs"]["perfect-empty"]["danger_recall"]
    assert diff["point"] == pytest.approx(1.0) and diff["low"] > 0


def test_full_human_sample_recovers_human_gold_exactly():
    """With every item human-labelled, N_k / n_k = 1 and PPI equals the human-gold value,
    whatever the committee got wrong (here: it missed every danger sign in stratum A)."""
    items, triage = _world()
    for t in triage.values():
        t["sampled"] = True
    committee = [_without_danger(i) if triage[i.item_id]["stratum"] == "A" else i for i in items]
    systems = {"perfect": _preds(items, "perfect", perfect=True)}
    out = run(committee, items, triage, systems, [], n_resamples=100)
    # Under committee gold the perfect system's true danger signs in A look like false alarms.
    r = out["systems"]["perfect"]["false_alarm_rate"]
    assert r["committee_only"] > 0
    assert r["ppi"]["point"] == pytest.approx(r["human_sample_only"]) == pytest.approx(0.0)


def test_safety_stop_when_committee_misses_danger_in_stratum_b():
    items, triage = _world()
    human = _sample(triage, items, every=1)
    committee = [_without_danger(i) if triage[i.item_id]["stratum"] == "B" else i for i in items]
    b_with_danger = [
        h for h in human if triage[h.item_id]["stratum"] == "B" and danger_positives(h.gold, DANGER)
    ]
    assert b_with_danger, "fixture needs a danger sign in stratum B"
    out = run(
        committee, human, triage, {"perfect": _preds(items, "p", perfect=True)}, [], n_resamples=50
    )
    assert out["safety_stop"]["triggered"] and out["systems"] == {}


def test_input_checks():
    items, triage = _world(2)
    human = _sample(triage, items)
    systems = {"p": _preds(items, "p", perfect=True)}
    not_sampled = next(i for i in items if not triage[i.item_id]["sampled"])
    with pytest.raises(InputError, match="seeded sample"):
        run(items, [*human, not_sampled], triage, systems, [], n_resamples=10)
    with pytest.raises(InputError, match="not in the committee"):
        run(items[1:], human, triage, systems, [], n_resamples=10)
    with pytest.raises(ValueError, match="no prediction"):
        run(items, human, triage, {"p": systems["p"][1:]}, [], n_resamples=10)


def test_cli_writes_results_and_exits_on_safety_stop(tmp_path):
    items, triage = _world()
    human = _sample(triage, items)

    def write(name, rows):
        p = tmp_path / name
        p.write_text("".join(r.model_dump_json() + "\n" for r in rows), encoding="utf-8")
        return p

    tri = tmp_path / "triage.jsonl"
    tri.write_text("".join(json.dumps(t) + "\n" for t in triage.values()), encoding="utf-8")
    args = [
        "--committee",
        str(write("c.jsonl", items)),
        "--triage",
        str(tri),
        "--human",
        str(write("h.jsonl", human)),
        "--pred",
        f"perfect={write('p.jsonl', _preds(items, 'perfect', perfect=True))}",
        "--resamples",
        "50",
        "--out",
        str(tmp_path / "out.json"),
    ]
    assert main(args) == 0
    assert json.loads((tmp_path / "out.json").read_text())["n_human"] == len(human)

    committee = [_without_danger(i) if triage[i.item_id]["stratum"] == "B" else i for i in items]
    for t in triage.values():
        t["sampled"] = True
    tri.write_text("".join(json.dumps(t) + "\n" for t in triage.values()), encoding="utf-8")
    args[1] = str(write("c2.jsonl", committee))
    args[5] = str(write("h2.jsonl", items))
    assert main(args) == SAFETY_EXIT
