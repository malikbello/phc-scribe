import json

from phc_scribe.asr_guard import THRESHOLD, compression_ratio, guard

LOOP = "she don dey bleed since morning " + "and the belle dey pain am " * 30
SPEECH = (
    "Madam, how body? Any bleeding? No bleeding. Baby dey move well well."
    " BP na one twenty over eighty. Come back in two weeks."
)


def test_a_loop_is_cut_to_two_copies():
    assert compression_ratio(LOOP) > THRESHOLD
    text, cut = guard(LOOP)
    assert cut
    assert text == "she don dey bleed since morning " + " ".join(["and the belle dey pain am"] * 2)


def test_ordinary_speech_is_untouched_even_with_real_repeats():
    assert guard(SPEECH) == (SPEECH, False)
    assert guard("") == ("", False)


def test_a_single_word_loop():
    assert guard("yes " * 60) == ("yes yes", True)


def test_rescore_script(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "asr_guard_rescore", Path(__file__).parents[1] / "scripts" / "asr_guard_rescore.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src, dst = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    rows = [
        {"audio_id": "a", "language": "pcm", "reference": "x", "text": LOOP},
        {"audio_id": "b", "language": "pcm", "reference": "x", "text": SPEECH},
    ]
    src.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert mod.main(src, dst) == {"clips": 2, "loops_cut": 1}
    got = [json.loads(x) for x in dst.read_text(encoding="utf-8").splitlines()]
    assert [g["guard_cut"] for g in got] == [True, False]
    assert got[1]["text"] == SPEECH


def test_publish_refuses_a_model_with_an_empty_tokenizer(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "publish_asr", Path(__file__).parents[1] / "scripts" / "publish_asr.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for f in mod.REQUIRED:
        (tmp_path / f).write_text("{}", encoding="utf-8")
    assert mod.incomplete(tmp_path) == []
    (tmp_path / "tokenizer.json").write_text("", encoding="utf-8")
    (tmp_path / "tokenizer_config.json").unlink()
    assert mod.incomplete(tmp_path) == ["tokenizer.json", "tokenizer_config.json"]
