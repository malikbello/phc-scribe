import shutil
from pathlib import Path

import pytest

from bench.freeze import Overlap, freeze, load_frozen_items
from bench.items import BenchItem, read_jsonl
from bench.notegen import generate
from bench.sft import build, example, label_mask

SMOKE = Path(__file__).parent / "fixtures" / "smoke_items.jsonl"


def test_freeze_detects_changes(tmp_path):
    test_file = tmp_path / "test.jsonl"
    shutil.copy(SMOKE, test_file)
    manifest = freeze([test_file], tmp_path)
    assert manifest.files[0].items == 6
    (tmp_path / "m.json").write_text(manifest.model_dump_json())
    assert len(load_frozen_items(tmp_path / "m.json", tmp_path)) == 6
    test_file.write_text(test_file.read_text() + "\n")
    with pytest.raises(ValueError, match="changed since the freeze"):
        load_frozen_items(tmp_path / "m.json", tmp_path)


def test_overlap_exact_and_near():
    base = (
        "G2P1 at 32 weeks. Complains of severe headache since yesterday and blurred vision."
        " BP 160/110. No bleeding."
    )
    o = Overlap([base])
    assert o.reason(base.upper()) == "exact duplicate of a test item"
    assert o.reason(base.replace("No bleeding.", "No leaking.")) == "near duplicate of a test item"
    assert o.reason("Booking visit, feels well, no complaints today, BP 110/70, Hb 11.") is None


def test_build_drops_test_overlap_and_keeps_generated():
    test = list(read_jsonl(SMOKE, BenchItem))
    train, _ = generate(20, seed=7)
    kept, dropped = build([*train, test[0]], test)
    assert len(kept) == 20
    assert dropped == [f"{test[0].item_id}: shares a group with a test item"]


def test_example_is_short_prompt_plus_gold():
    item = next(iter(read_jsonl(SMOKE, BenchItem)))
    ex = example(item)
    roles = [m["role"] for m in ex["messages"]]
    assert roles == ["system", "user", "assistant"]
    assert len(ex["messages"][0]["content"]) < 400
    assert '"start"' not in ex["messages"][2]["content"]


def test_label_mask():
    assert label_mask([1, 2], [1, 2, 3, 4]) == [-100, -100, 3, 4]
    with pytest.raises(ValueError):
        label_mask([1, 9], [1, 2, 3])
