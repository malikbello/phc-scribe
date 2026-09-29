import unicodedata

from phc_scribe.text import fold, fold_text, normalise


def test_normalise_composes():
    decomposed = "ẹ̀jẹ̀"  # ẹ̀jẹ̀ fully decomposed
    assert normalise(decomposed) == unicodedata.normalize("NFC", decomposed)


def test_fold_removes_tone_marks_and_underdots():
    assert fold_text(normalise("Ẹ̀jẹ̀ ń jáde")) == "eje n jade"


def test_fold_keep_underdot_only_removes_tones():
    assert fold_text(normalise("ẹ̀jẹ̀ ọ̀sẹ̀"), keep_underdot=True) == "ẹjẹ ọsẹ"


def test_fold_collapses_whitespace_and_maps_quotes():
    assert fold_text("BP  140/90\n‘high’") == "bp 140/90 'high'"


def test_folded_span_maps_back_to_source_including_trailing_tone_mark():
    source = normalise("Ó ní ẹ̀jẹ̀ ń jáde.")
    f = fold(source)
    i = f.text.index("eje")
    start, end = f.to_source_span(i, i + 3)
    assert source[start:end] == normalise("ẹ̀jẹ̀")


def test_folded_index_is_monotonic_and_in_range():
    source = normalise("Orí ń fọ́ mi gidigidi,   ẹsẹ̀ mi wú")
    f = fold(source)
    assert len(f.index) == len(f.text)
    assert list(f.index) == sorted(f.index)
    assert all(0 <= i < len(source) for i in f.index)
