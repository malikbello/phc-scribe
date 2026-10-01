from bench.items import Prediction
from bench.label_queue import SourceRow
from bench.teacher import filter_teacher, to_items
from phc_scribe.encounter import Encounter


def _rows(n: int, lang: str = "pcm") -> list[SourceRow]:
    return [
        SourceRow(
            source="wazobia",
            source_id=f"{lang}-{i}",
            speaker_id=f"S{i % 3}",
            language=lang,  # type: ignore[arg-type]
            split="train",
            transcript=f"my belle dey pain me {i}" if i % 2 else f"drink water every day {i}",
        )
        for i in range(n)
    ]


def _record(quote: str | None) -> Encounter:
    if quote is None:
        return Encounter()
    return Encounter.model_validate(
        {
            "findings": [
                {"concept": "abdominal_pain", "assertion": "present", "evidence": {"text": quote}}
            ]
        }
    )


def test_to_items_samples_train_rows_as_stratum_t():
    items = to_items(_rows(20), per_language=6, enriched_share=0.5)
    assert len(items) == 6
    assert {i.stratum for i in items} == {"T"} and all(not i.gold.findings for i in items)
    assert all(i.group_id.startswith("wazobia:S") for i in items)


def test_filter_keeps_only_valid_verbatim_labels_and_caps_empty():
    items = to_items(_rows(10), per_language=10, enriched_share=0.5)
    preds = []
    for it in items:
        pain = "belle dey pain" in it.transcript
        if it.item_id.endswith("-1"):
            preds.append(Prediction(item_id=it.item_id, system="t", record=None))  # invalid
        elif it.item_id.endswith("-3"):
            preds.append(
                Prediction(item_id=it.item_id, system="t", record=_record("belle dey ache"))
            )
        else:
            preds.append(
                Prediction(
                    item_id=it.item_id,
                    system="t",
                    record=_record("belle dey pain" if pain else None),
                )
            )
    kept, report = filter_teacher(items, preds)
    assert report.invalid == 1 and report.ungrounded == 1
    assert report.kept_with_findings == 3  # odd ids 5, 7, 9
    assert report.kept_empty == 3 and report.empty_over_cap == 2  # capped at half of kept
    assert len(kept) == 6
    quotes = [f.evidence.text for k in kept for f in k.gold.findings if f.evidence]
    assert quotes == ["belle dey pain"] * 3
