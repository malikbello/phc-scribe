"""Supervised fine-tuning examples: the fine-tuned rung's short prompt plus the gold
record as the assistant turn. Only the assistant tokens are trained (see label_mask)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from bench.freeze import Overlap, TestItem
from bench.items import BenchItem
from bench.prompts import build_messages, record_json


def example(item: BenchItem) -> dict:
    messages = build_messages(item.transcript, "finetuned")
    messages.append({"role": "assistant", "content": record_json(item.gold)})
    return {
        "item_id": item.item_id,
        "origin": item.origin,
        "language": item.language,
        "messages": messages,
    }


def build(
    items: Sequence[BenchItem], test: Sequence[TestItem | BenchItem]
) -> tuple[list[dict], list[str]]:
    """Training examples, and the ids dropped for overlapping the frozen test set."""
    overlap = Overlap(t.transcript for t in test)
    test_groups = {t.group_id for t in test}
    kept, dropped = [], []
    for item in items:
        why = "shares a group with a test item" if item.group_id in test_groups else None
        why = why or overlap.reason(item.transcript)
        if why:
            dropped.append(f"{item.item_id}: {why}")
        else:
            kept.append(example(item))
    return kept, dropped


def label_mask(prompt_ids: Sequence[int], full_ids: Sequence[int]) -> list[int]:
    """Labels for causal-LM training: -100 (ignored) on the prompt, token ids on the answer."""
    if list(full_ids[: len(prompt_ids)]) != list(prompt_ids):
        raise ValueError("the prompt tokens are not a prefix of the full example")
    return [-100] * len(prompt_ids) + list(full_ids[len(prompt_ids) :])


# Safety-weighted loss (ADR-0024, stage 1). The clinical meaning of a record sits in a
# few tokens: each finding's concept and assertion. The rest is JSON boilerplate.
_CRITICAL = re.compile(r'"(?:concept|assertion)": "([^"]*)"')


def critical_char_spans(answer: str) -> list[tuple[int, int]]:
    """Character spans of every concept and assertion value in a gold JSON answer."""
    return [m.span(1) for m in _CRITICAL.finditer(answer)]


def token_weights(
    offsets: Sequence[tuple[int, int]],
    spans: Sequence[tuple[int, int]],
    weight: float,
    shift: int = 0,
) -> list[float]:
    """Per-token loss weights: `weight` for a token overlapping any span (spans are relative
    to the answer, which starts at character `shift` of the tokenised text), else 1."""
    absolute = [(a + shift, b + shift) for a, b in spans]
    out = []
    for start, end in offsets:
        hit = end > start and any(start < b and a < end for a, b in absolute)
        out.append(weight if hit else 1.0)
    return out
