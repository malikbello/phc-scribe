import yaml

from bench.redteam import SOURCE, build


def test_redteam_gold_is_exact_and_covers_every_failure_mode():
    spec = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    items = build(spec)
    assert len(items) == len(spec["items"]) == len({i.item_id for i in items})
    assert {i.language for i in items} == {"en", "yo", "pcm"}
    categories = {row["category"] for row in spec["items"]}
    assert {"negation_list", "embedded_instruction", "third_party", "past_vs_current"} <= categories
    injected = [i for i in items if "inject" in i.item_id]
    assert injected and all(not i.gold.findings for i in injected)
