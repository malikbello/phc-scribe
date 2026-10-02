import json
import shutil
from pathlib import Path

import pytest

from bench.freeze import (
    Overlap,
    freeze_items,
    freeze_labels,
    load_frozen_items,
    load_gold_items,
)
from bench.items import BenchItem, read_jsonl
from bench.notegen import generate
from bench.sft import build, example, label_mask

SMOKE = Path(__file__).parent / "fixtures" / "smoke_items.jsonl"


def _queue_from(bench_file: Path, out: Path) -> None:
    """A label queue holding the same items as a benchmark file, without gold."""
    rows = [json.loads(line) for line in bench_file.read_text().splitlines() if line.strip()]
    out.write_text(
        "".join(
            json.dumps({k: r[k] for k in ("item_id", "group_id", "language", "transcript")}) + "\n"
            for r in reversed(rows)
        )
    )


def test_stage1_freezes_items_not_labels(tmp_path):
    test_file = tmp_path / "test.jsonl"
    shutil.copy(SMOKE, test_file)
    manifest = freeze_items([test_file], tmp_path)
    assert manifest.stage == 1 and manifest.files[0].items == 6
    assert manifest.files[0].sha256 is None
    (tmp_path / "m.json").write_text(manifest.model_dump_json())
    assert len(load_frozen_items(tmp_path / "m.json", tmp_path)) == 6
    # editing gold is allowed before stage 2; editing items is not
    rows = [json.loads(line) for line in test_file.read_text().splitlines() if line.strip()]
    test_file.write_text("".join(json.dumps(r) + "\n" for r in rows[::-1]))
    assert len(load_frozen_items(tmp_path / "m.json", tmp_path)) == 6
    rows[0]["transcript"] += " changed"
    test_file.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError, match="items changed since the freeze"):
        load_frozen_items(tmp_path / "m.json", tmp_path)
    with pytest.raises(ValueError, match="labels are not frozen"):
        load_gold_items(tmp_path / "m.json", tmp_path)


def test_stage2_swaps_queue_for_labelled_file_and_locks_gold(tmp_path):
    queue = tmp_path / "queue.jsonl"
    _queue_from(SMOKE, queue)
    stage1 = freeze_items([queue], tmp_path)
    labelled = tmp_path / "gold.jsonl"
    shutil.copy(SMOKE, labelled)
    stage2 = freeze_labels(stage1, tmp_path, {"queue.jsonl": labelled})
    assert stage2.stage == 2 and stage2.frozen_at == stage1.frozen_at
    assert stage2.files[0].path == "gold.jsonl"
    assert stage2.files[0].items_sha256 == stage1.files[0].items_sha256
    (tmp_path / "m.json").write_text(stage2.model_dump_json())
    assert len(load_gold_items(tmp_path / "m.json", tmp_path)) == 6
    with pytest.raises(ValueError, match="already frozen"):
        freeze_labels(stage2, tmp_path)
    labelled.write_text(labelled.read_text() + "\n")
    with pytest.raises(ValueError, match="changed since the labels were frozen"):
        load_gold_items(tmp_path / "m.json", tmp_path)


def test_stage2_refuses_different_items(tmp_path):
    queue = tmp_path / "queue.jsonl"
    _queue_from(SMOKE, queue)
    lines = queue.read_text().splitlines()
    queue.write_text("\n".join(lines[1:]) + "\n")
    stage1 = freeze_items([queue], tmp_path)
    with pytest.raises(ValueError, match="does not hold the items"):
        freeze_labels(stage1, tmp_path, {"queue.jsonl": SMOKE})


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


def test_stage2_records_declared_exclusions_only(tmp_path):
    queue = tmp_path / "queue.jsonl"
    _queue_from(SMOKE, queue)
    stage1 = freeze_items([queue], tmp_path)
    rows = SMOKE.read_text().splitlines()
    gone = json.loads(rows[0])["item_id"]
    labelled = tmp_path / "gold.jsonl"
    labelled.write_text("\n".join(rows[1:]) + "\n")
    with pytest.raises(ValueError, match="does not hold the items"):
        freeze_labels(stage1, tmp_path, {"queue.jsonl": labelled})
    stage2 = freeze_labels(
        stage1, tmp_path, {"queue.jsonl": labelled}, excluded={"queue.jsonl": [gone]}
    )
    assert stage2.files[0].excluded == [gone] and stage2.files[0].items == 5
    assert stage2.files[0].frozen_as == "queue.jsonl"
    (tmp_path / "m.json").write_text(stage2.model_dump_json())
    assert len(load_frozen_items(tmp_path / "m.json", tmp_path)) == 5


def test_critical_spans_cover_concept_and_assertion_values_only():
    from bench.sft import critical_char_spans

    answer = (
        '{"findings": [{"concept": "fever", "assertion": "present", "evidence": {"text": "hot"}}]}'
    )
    assert [answer[a:b] for a, b in critical_char_spans(answer)] == ["fever", "present"]


def test_token_weights_mark_overlapping_tokens_with_shift():
    from bench.sft import token_weights

    # text = "<pre>" + answer; answer chars 2-7 are critical
    offsets = [(0, 5), (5, 7), (7, 12), (12, 14), (0, 0)]
    w = token_weights(offsets, [(2, 7)], weight=3.0, shift=5)
    assert w == [1.0, 1.0, 3.0, 1.0, 1.0]  # special tokens (empty span) stay at 1
