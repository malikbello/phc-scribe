"""Word error rate for ASR checks: word-level edit distance over folded text (case, tone marks
and punctuation removed, as in bench.two_view.fold). Reports also keep the raw counts, so a
corpus WER is sum(errors) / sum(reference words), not a mean of per-clip rates."""

from __future__ import annotations

from bench.two_view import fold


def edit_errors(reference: str, hypothesis: str) -> tuple[int, int]:
    """(word edits, reference words) between two texts, after folding."""
    ref, hyp = fold(reference).split(), fold(hypothesis).split()
    row = list(range(len(hyp) + 1))
    for i in range(1, len(ref) + 1):
        prev, row[0] = row[0], i
        for j in range(1, len(hyp) + 1):
            cur = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1, prev + (ref[i - 1] != hyp[j - 1]))
            prev = cur
    return row[len(hyp)], len(ref)


def corpus_wer(pairs: list[tuple[str, str]]) -> float | None:
    errors = words = 0
    for ref, hyp in pairs:
        e, n = edit_errors(ref, hyp)
        errors, words = errors + e, words + n
    return errors / words if words else None
