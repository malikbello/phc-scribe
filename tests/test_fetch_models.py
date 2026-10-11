"""fetch_models refuses an incomplete int8 build (ADR-0032): every file CTranslate2 and the
Whisper processor need, with either name of the feature-extractor config."""

from phc_scribe.fetch_models import int8_incomplete


def _folder(path, names):
    path.mkdir()
    for n in names:
        (path / n).write_text("x")
    return path


def test_int8_build_needs_weights_vocabulary_tokenizer_and_feature_config(tmp_path):
    core = ["model.bin", "config.json", "vocabulary.json", "tokenizer.json"]
    assert int8_incomplete(_folder(tmp_path / "a", [*core, "processor_config.json"])) == []
    assert int8_incomplete(_folder(tmp_path / "b", [*core, "preprocessor_config.json"])) == []
    # the first conversion of the fine-tunes left the feature-extractor config out (11 Oct)
    assert int8_incomplete(_folder(tmp_path / "c", core)) == [
        "preprocessor_config.json or processor_config.json"
    ]
    assert "model.bin" in int8_incomplete(
        _folder(tmp_path / "d", [*core[1:], "processor_config.json"])
    )
