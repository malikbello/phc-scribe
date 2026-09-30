"""Supervised fine-tuning examples: the fine-tuned rung's short prompt plus the gold
record as the assistant turn. Only the assistant tokens are trained (see label_mask)."""

from __future__ import annotations

from collections.abc import Sequence

from bench.freeze import Overlap
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


def build(items: Sequence[BenchItem], test: Sequence[BenchItem]) -> tuple[list[dict], list[str]]:
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
