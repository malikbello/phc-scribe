"""Two views of each training clip (ADR-0024, stage 0): the human transcript and N-ATLaS ASR.

The shipped system reads ASR output, but teacher labels sit on human transcripts. For each
labelled clip we add a second item whose transcript is the ASR hypothesis and whose gold is
the same record, with every evidence quote moved onto the matching words of the ASR text.
- A quote is moved only if a window of ASR words matches it closely (after folding case,
  tone marks and punctuation); the evidence is then the ASR words exactly as they appear,
  so grounding stays verbatim.
- If any finding's quote cannot be found, the ASR view of that clip is dropped. A partial
  record would teach the model to miss findings.
- The ASR view keeps the clip's group id, so both views land on the same side of the dev
  split and never leak across it.
Pure functions; the ASR itself runs on Kaggle (bench/asr_train.py).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from difflib import SequenceMatcher

from pydantic import BaseModel

from bench.items import BenchItem
from phc_scribe.grounding import ground

MIN_SIMILARITY = 0.75
TIE = 0.03  # scores this close count as equal
_WORD = re.compile(r"\S+")


def fold(text: str) -> str:
    """Lowercase, strip tone marks and dot-below, keep letters and digits."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    bare = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^\w\s]", "", bare).strip()


def relocate(quote: str, asr: str, min_similarity: float = MIN_SIMILARITY) -> str | None:
    """The ASR words that best match `quote`, verbatim from `asr`, or None if nothing is
    close enough. Windows of the quote's length ±2 words are compared on folded text."""
    target = fold(quote)
    words = [(m.start(), m.end(), fold(m.group())) for m in _WORD.finditer(asr)]
    n = len(target.split())
    if not target or not words or not n:
        return None
    candidates: list[tuple[float, int, tuple[int, int]]] = []
    for size in range(max(1, n - 2), n + 3):
        for i in range(0, max(0, len(words) - size) + 1):
            window = words[i : i + size]
            text = " ".join(w for _, _, w in window if w)
            score = SequenceMatcher(None, target, text).ratio()
            candidates.append((score, abs(len(text) - len(target)), (window[0][0], window[-1][1])))
    if not candidates:
        return None
    best = max(c[0] for c in candidates)
    if best < min_similarity:
        return None
    # Among near-equal matches prefer the one closest in length to the quote, so a leading
    # word the ASR spelt differently (a negation cue, "the" -> "di") is kept, not trimmed.
    near = [c for c in candidates if c[0] >= best - TIE]
    _, _, (start, end) = min(near, key=lambda c: (c[1], -c[0]))
    return asr[start:end]


class TwoViewReport(BaseModel):
    items: int = 0
    no_asr: int = 0
    empty_asr: int = 0
    quote_not_found: int = 0
    added: int = 0


def audio_id(item: BenchItem) -> str:
    """WazobiaSpeech audio id of a teacher item (`t-<lang>-<audio_id>`)."""
    return item.item_id.split("-", 2)[2]


def asr_views(
    items: Sequence[BenchItem], asr: Mapping[str, str]
) -> tuple[list[BenchItem], TwoViewReport]:
    report = TwoViewReport(items=len(items))
    out: list[BenchItem] = []
    for item in items:
        text = asr.get(audio_id(item))
        if text is None:
            report.no_asr += 1
            continue
        if not text.strip():
            report.empty_asr += 1
            continue
        findings = []
        for f in item.gold.findings:
            moved = relocate(f.evidence.text, text) if f.evidence else None
            if f.evidence and moved is None:
                break
            ev = (
                f.evidence.model_copy(update={"text": moved, "start": None, "end": None})
                if f.evidence
                else None
            )
            findings.append(f.model_copy(update={"evidence": ev}))
        else:
            gold = item.gold.model_copy(update={"findings": findings})
            g = ground(gold, text)
            if g.dropped or g.folded_matches:
                report.quote_not_found += 1
                continue
            out.append(
                item.model_copy(
                    update={"item_id": f"{item.item_id}-asr", "transcript": text, "gold": g.record}
                )
            )
            report.added += 1
            continue
        report.quote_not_found += 1
    return out, report
