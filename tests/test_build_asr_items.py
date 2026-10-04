import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_asr_items import asr_items

from bench.items import BenchItem
from phc_scribe.encounter import Encounter


def _item(audio_id: str) -> BenchItem:
    gold = Encounter.model_validate(
        {"findings": [{"concept": "fever", "assertion": "present", "evidence": {"text": "ibà"}}]}
    )
    return BenchItem(
        item_id=f"s4w-yo-{audio_id}",
        group_id="wazobia:S1",
        stratum="S4W",
        language="yo",
        origin="real",
        transcript="ibà ń ṣe mí",
        gold=gold,
    )


def test_asr_items_keep_gold_and_swap_text():
    items, missing = asr_items([_item("a_1"), _item("a_2")], {"a_1": "iba n se mi"}, "asr-")
    assert missing == ["s4w-yo-a_2"]
    assert items[0].transcript == "iba n se mi" and items[0].item_id == "asr-s4w-yo-a_1"
    assert items[0].gold.findings[0].concept == "fever"
