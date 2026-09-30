# ruff: noqa: E501  (prompt prose is kept on one line per rule so the model sees it unwrapped)
"""Prompts for the model rungs of the baseline ladder (docs/eval-plan.md, section 2).

Every model rung gets the same instructions and the same schema-constrained decoding;
rungs differ only in the model and in zero-shot vs few-shot. Few-shot examples come
from the constructed smoke fixtures, which are never part of any test stratum.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from bench.items import BenchItem, read_jsonl
from phc_scribe.encounter import Encounter
from phc_scribe.vocab import load_vocabulary

Mode = Literal["zeroshot", "fewshot"]
FEWSHOT_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "smoke_items.jsonl"
FEWSHOT_IDS = ("smoke-001-en", "smoke-003-yo")
PROMPT_VERSION = "prompt-v0.1"


def _vocabulary_block() -> str:
    vocab = load_vocabulary()
    lines = []
    for c in vocab.concepts:
        tag = " [DANGER SIGN]" if c.danger_sign else ""
        lines.append(f"- {c.id}: {c.label_en}{tag}. {c.definition}")
    return "\n".join(lines)


SYSTEM_TEMPLATE = """You are a clinical documentation assistant for antenatal care (ANC) visits in Nigerian primary health centres. You turn what was said or written at a visit (English, Nigerian Pidgin or Yoruba, often mixed) into a structured JSON record. You never give advice or a diagnosis.

Rules:
1. Record only what the text states. Never infer or diagnose.
2. Every value needs "evidence": a short quote copied exactly from the text (same spelling and tone marks).
3. Findings use only these concept ids:
{vocabulary}
4. Assertion: "present" (now, this pregnancy), "absent" (denied or negated; include the cue, e.g. "no bleeding"), "possible" (hedged or uncertain), "historical" (previous pregnancy or the past). Do not list concepts that are not mentioned.
5. Use a severe concept only when the text says severe, very bad, persistent or similar; otherwise use the mild one.
6. Only the pregnant woman's own findings. Ignore other people's symptoms.
7. Numbers: blood pressure as systolic/diastolic, gestational age in weeks, only when stated.
Output only the JSON record."""


def system_prompt() -> str:
    return SYSTEM_TEMPLATE.format(vocabulary=_vocabulary_block())


def _record_json(record: Encounter) -> str:
    data = record.model_dump(mode="json", exclude_none=True, exclude_defaults=False)

    def strip_offsets(x: object) -> object:
        if isinstance(x, dict):
            return {k: strip_offsets(v) for k, v in x.items() if k not in ("start", "end")}
        if isinstance(x, list):
            return [strip_offsets(v) for v in x]
        return x

    return json.dumps(strip_offsets(data), ensure_ascii=False)


def _fewshot_examples() -> list[BenchItem]:
    items = {i.item_id: i for i in read_jsonl(FEWSHOT_PATH, BenchItem)}
    return [items[i] for i in FEWSHOT_IDS]


def user_prompt(transcript: str) -> str:
    return f"Visit text:\n<<<\n{transcript}\n>>>\nReturn the JSON record."


def build_messages(transcript: str, mode: Mode) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt()}]
    if mode == "fewshot":
        for ex in _fewshot_examples():
            messages.append({"role": "user", "content": user_prompt(ex.transcript)})
            messages.append({"role": "assistant", "content": _record_json(ex.gold)})
    messages.append({"role": "user", "content": user_prompt(transcript)})
    return messages
