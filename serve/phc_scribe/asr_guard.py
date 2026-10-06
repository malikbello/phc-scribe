"""Decoding guard for the ASR output (audit H4): stop a looping transcript reaching the record.

Whisper-family models sometimes fall into a loop and repeat a phrase until the token limit
(the fine-tuned Pidgin model wrote 222 words for a 23-word clip). Whisper's own check is the
gzip compression ratio of the text: normal speech compresses to about 1.5-2, a loop to well
above 2.4. When the ratio is above that threshold, every run of a repeated word n-gram
(n = 1..8) longer than ``MAX_REPEATS`` is cut back to ``MAX_REPEATS`` copies. Speech that
really repeats a word ("very very") keeps up to two copies, and text below the threshold is
returned unchanged, so ordinary transcripts are never touched.

Deterministic and text-only, so the same function runs in serving
(serve/phc_scribe/api/asr.py) and when re-scoring saved transcripts
(scripts/asr_guard_rescore.py): what is scored is what ships.
"""

from __future__ import annotations

import zlib

THRESHOLD = 2.4  # Whisper's default compression_ratio_threshold
MAX_REPEATS = 2
MAX_N = 8


def compression_ratio(text: str) -> float:
    data = text.encode("utf-8")
    return len(data) / len(zlib.compress(data)) if data else 0.0


def _collapse(words: list[str]) -> list[str]:
    for n in range(1, MAX_N + 1):
        out: list[str] = []
        i = 0
        while i < len(words):
            gram = words[i : i + n]
            run = 1
            if len(gram) == n:
                while words[i + run * n : i + (run + 1) * n] == gram:
                    run += 1
            if run > 1:
                out.extend(gram * min(run, MAX_REPEATS))
                i += run * n
            else:
                out.append(words[i])
                i += 1
        words = out
    return words


def guard(text: str) -> tuple[str, bool]:
    """Return the guarded text and whether a loop was cut."""
    if compression_ratio(text) <= THRESHOLD:
        return text, False
    cut = " ".join(_collapse(text.split()))
    return cut, cut != " ".join(text.split())
