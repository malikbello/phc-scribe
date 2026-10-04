import yaml

from bench.constructed import LEXICON, SEVERITY_PAIRS, build, summary
from phc_scribe.vocab import load_vocabulary


def _items(per_language: int = 60, seed: int = 1):
    return build(yaml.safe_load(LEXICON.read_text(encoding="utf-8")), per_language, seed)


def test_gold_is_exact_by_construction():
    vocab = load_vocabulary()
    for item in _items():
        for f in item.gold.findings:
            assert str(f.concept) in vocab.ids
            assert f.evidence and f.evidence.text in item.transcript
        concepts = {str(f.concept) for f in item.gold.findings}
        assert len(concepts) == len(item.gold.findings)  # one assertion per concept
        for a, b in SEVERITY_PAIRS:
            assert not {a, b} <= concepts  # severe and mild never together


def test_mix_and_determinism():
    items = _items(per_language=100)
    report = summary(items)
    for lang in ("yo", "pcm"):
        assert report[lang]["items"] == 100
        assert report[lang]["items_with_danger_sign"] == 52
        assert report[lang]["nothing_to_record"] >= 18
        assert len(report[lang]["danger_concepts"]) >= 10  # rare signs are covered
    again = _items(per_language=100)
    assert [i.transcript for i in items] == [i.transcript for i in again]


def test_lexicon_has_no_health_worker_only_signs():
    lexicon = yaml.safe_load(LEXICON.read_text(encoding="utf-8"))
    for lang in lexicon["languages"].values():
        assert "looks_very_ill" not in lang["concepts"]  # cannot come from patient speech
        assert "severe_pallor" not in lang["concepts"]
