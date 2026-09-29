"""Transcript text handling: Unicode NFC and diacritic folding with offset maps.

Yoruba writes tone with combining marks (grave, acute, macron) and some vowels and
consonants with a dot below (ẹ, ọ, ṣ). ASR output and keyboards drop some or all of
them, so matching runs on a folded copy while offsets still point into the original
NFC text. Offsets are Unicode code points in the NFC transcript.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

TONE_MARKS = frozenset({"̀", "́", "̄"})  # grave, acute, macron
UNDERDOT = "̣"

_PUNCT_MAP = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
}


def normalise(text: str) -> str:
    """Canonical form for every transcript the system stores or quotes: Unicode NFC."""
    return unicodedata.normalize("NFC", text)


@dataclass(frozen=True)
class Folded:
    """A folded string plus, for each folded character, its offset in the source."""

    text: str
    source: str
    index: tuple[int, ...]

    def to_source_span(self, start: int, end: int) -> tuple[int, int]:
        """Map a half-open span in the folded text back to the source string.

        The end is extended over trailing combining marks so a span never splits a
        base letter from its tone mark.
        """
        if not 0 <= start < end <= len(self.text):
            raise ValueError(f"span {start}:{end} outside folded text of length {len(self.text)}")
        src_start = self.index[start]
        src_end = self.index[end - 1] + 1
        while src_end < len(self.source) and unicodedata.combining(self.source[src_end]):
            src_end += 1
        return src_start, src_end


def fold(text: str, *, keep_underdot: bool = False, lower: bool = True) -> Folded:
    """Fold ``text`` for matching.

    Always removes tone marks, collapses whitespace runs to one space and maps curly
    quotes and dashes to ASCII. ``keep_underdot=True`` keeps ẹ/ọ/ṣ distinct from e/o/s
    (the "tone-mark folding" used in evaluation); the default removes every combining
    mark, which is what robust matching needs.
    """
    out: list[str] = []
    index: list[int] = []
    for i, ch in enumerate(text):
        if ch.isspace():
            if out and out[-1] == " ":
                continue
            out.append(" ")
            index.append(i)
            continue
        ch = _PUNCT_MAP.get(ch, ch)
        kept = [
            d
            for d in unicodedata.normalize("NFD", ch)
            if not unicodedata.combining(d) or (keep_underdot and d == UNDERDOT)
        ]
        piece = unicodedata.normalize("NFC", "".join(kept))
        if lower:
            piece = piece.lower()
        for c in piece:
            out.append(c)
            index.append(i)
    return Folded(text="".join(out), source=text, index=tuple(index))


def fold_text(text: str, *, keep_underdot: bool = False) -> str:
    """Folded string only (no offsets)."""
    return fold(text, keep_underdot=keep_underdot).text
