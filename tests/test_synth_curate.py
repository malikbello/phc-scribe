from bench.synth_curate import RELABEL, concept_named, curate


def test_curate_rejects_relabels_and_dedupes():
    text = next(iter(RELABEL))
    rows = [
        {
            "id": "a",
            "language": "en",
            "concept": "reduced_fetal_movement",
            "assertion": "absent",
            "text": text,
            "kept": True,
        },
        {
            "id": "b",
            "language": "en",
            "concept": "fever",
            "assertion": "present",
            "text": "I have a fever now.",
            "kept": True,
        },
        {
            "id": "c",
            "language": "en",
            "concept": "fever",
            "assertion": "present",
            "text": "I have a fever now.",
            "kept": True,
        },
        {
            "id": "d",
            "language": "yo",
            "concept": "fever",
            "assertion": "present",
            "text": "Ara mi ń gbóná.",
            "kept": True,
        },
    ]
    out = curate(rows)
    assert [r["id"] for r in out] == ["a", "b"]
    assert (out[0]["concept"], out[0]["assertion"]) == RELABEL[text]


def test_concept_named():
    assert concept_named("unconscious", "I fainted yesterday")
    assert not concept_named("leaking_amniotic_fluid", "I am tired")
    assert concept_named(None, "anything")
