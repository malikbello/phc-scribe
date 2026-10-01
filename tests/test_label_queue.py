import importlib.util
from pathlib import Path
from typing import Any

from bench.label_queue import Label, QueueItem, SourceRow, build_items, sample_queue
from phc_scribe.encounter import Assertion, Evidence, Finding

ROOT = Path(__file__).resolve().parents[1]


def _rows(lang: Any = "yo", n=10, speaker_mod=3):
    return [
        SourceRow(
            source="mamai",
            source_id=f"{lang}{i:03d}",
            speaker_id=f"spk{i % speaker_mod}",
            language=lang,
            split="test",
            transcript=f"Mo ni ẹ̀jẹ̀ ní oyún mi {i}" if i else "  ",
        )
        for i in range(n)
    ]


def test_sample_is_seeded_stratified_and_order_independent():
    rows = _rows("yo") + _rows("pcm")
    a = sample_queue(rows, {"yo": 4, "pcm": 3}, seed=7)
    b = sample_queue(list(reversed(rows)), {"yo": 4, "pcm": 3}, seed=7)
    assert [q.item_id for q in a] == [q.item_id for q in b]
    assert sum(q.language == "yo" for q in a) == 4
    assert sum(q.language == "pcm" for q in a) == 3
    assert all(q.transcript.strip() for q in a)  # the empty transcript is dropped
    assert a[0].group_id.startswith("mamai:spk")
    c = sample_queue(rows, {"yo": 4, "pcm": 3}, seed=8)
    assert [q.item_id for q in a] != [q.item_id for q in c]


def _queue_item(text="Blood dey comot for my body, no headache"):
    return QueueItem(
        item_id="s4-pcm-1",
        group_id="mamai:spk1",
        language="pcm",
        source="mamai",
        source_id="1",
        transcript=text,
    )


def _label(findings, at="2026-10-01T10:00:00Z", status: Any = "labelled"):
    return Label(
        item_id="s4-pcm-1",
        status=status,
        findings=findings,
        labeller="malik",
        labelled_at=at,
        skip_reason="unintelligible" if status == "skip" else None,
    )


def _f(concept, assertion, text):
    return Finding(concept=concept, assertion=Assertion(assertion), evidence=Evidence(text=text))


def test_build_items_uses_latest_label_and_checks_evidence():
    q = _queue_item()
    old = _label([_f("headache", "present", "headache")], at="2026-10-01T09:00:00Z")
    new = _label(
        [
            _f("vaginal_bleeding", "present", "Blood dey comot for my body"),
            _f("headache", "absent", "no headache"),
        ]
    )
    items, report = build_items([q], [new, old])
    assert report.items == 1 and not report.errors
    item = items[0]
    assert item.stratum == "S4" and item.origin == "real" and item.language == "pcm"
    assert {(f.concept, f.assertion) for f in item.gold.findings} == {
        ("vaginal_bleeding", Assertion.present),
        ("headache", Assertion.absent),
    }


def test_build_items_reports_bad_evidence_skips_and_unknown_ids():
    q = _queue_item()
    bad = _label([_f("fever", "present", "hot body")])
    items, report = build_items([q], [bad])
    assert not items and "not found verbatim" in report.errors[0]

    items, report = build_items([q], [_label([], status="skip")])
    assert not items and report.skipped == 1

    items, report = build_items([q], [])
    assert report.unlabelled == 1

    stray = _label([]).model_copy(update={"item_id": "s4-yo-999"})
    _, report = build_items([q], [stray])
    assert any("not in the queue" in e for e in report.errors)


def test_empty_label_is_a_valid_no_findings_item():
    items, report = build_items([_queue_item()], [_label([])])
    assert report.items == 1 and items[0].gold.findings == []


def test_committed_labeler_matches_vocabulary():
    spec = importlib.util.spec_from_file_location(
        "build_labeler", ROOT / "scripts" / "build_labeler.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = (ROOT / "tools" / "labeler" / "labeler.html").read_text(encoding="utf-8")
    assert committed == module.render(), "run: python scripts/build_labeler.py"


def test_enrichment_matches_folded_whole_words():
    from bench.label_queue import enriched

    assert enriched("Ẹ̀jẹ̀ ń jáde lára mi")  # tone marks and under-dots folded
    assert enriched("mo ti lóyún oṣù mẹ́ta")
    assert enriched("my belle dey pain me")
    assert not enriched("fitness training every morning")  # whole words only
    assert not enriched("the market price of rice")


def test_enriched_queue_splits_groups_and_backfills():
    from bench.label_queue import sample_enriched_queue

    rows = [
        SourceRow(
            source="wazobia",
            source_id=f"e{i}",
            speaker_id=f"s{i}",
            language="yo",
            split="dev_test",
            transcript=f"ẹ̀jẹ̀ {i}",
        )
        for i in range(5)
    ] + [
        SourceRow(
            source="wazobia",
            source_id=f"r{i}",
            speaker_id=f"s{i}",
            language="yo",
            split="dev_test",
            transcript=f"ọjà {i}",
        )
        for i in range(20)
    ]
    q = sample_enriched_queue(rows, {"yo": 10}, enriched_share=0.6, seed=1)
    assert len(q) == 10
    # only 5 enriched clips exist, so the random group fills the rest
    assert sum(x.sampling == "enriched" for x in q) == 5
    assert sum(x.sampling == "random" for x in q) == 5
    assert all(x.item_id.startswith("s4w-yo-") for x in q)
    again = sample_enriched_queue(list(reversed(rows)), {"yo": 10}, enriched_share=0.6, seed=1)
    assert [x.item_id for x in q] == [x.item_id for x in again]
