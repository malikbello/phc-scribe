"""Benchmark item and prediction records (JSONL on disk, never committed with real text)."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from phc_scribe.encounter import Encounter

Stratum = Literal["S1", "S2", "S3", "S4", "S4W", "G", "R", "H", "T", "pilot", "smoke"]
Origin = Literal["real", "translated", "constructed", "generated"]
Language = Literal["en", "yo", "pcm", "ha", "ig"]
T = TypeVar("T", bound=BaseModel)


class BenchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    group_id: str = Field(description="Source-note group; a note and its translation share it.")
    stratum: Stratum
    language: Language
    origin: Origin
    transcript: str
    gold: Encounter


class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    system: str
    raw_output: str | None = None
    record: Encounter | None = Field(
        default=None, description="Parsed output before grounding; None if schema-invalid."
    )
    error: str | None = None
    latency_ms: float | None = None
    prompt_tokens: int | None = None


def read_jsonl(path: Path, model: type[T]) -> Iterator[T]:
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if line.strip():
                try:
                    yield model.model_validate_json(line)
                except ValueError as e:
                    raise ValueError(f"{path}:{line_no}: {e}") from e


def write_jsonl(path: Path, rows: Iterable[BaseModel]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row.model_dump(mode="json", exclude_none=True), ensure_ascii=False))
            f.write("\n")
            n += 1
    return n
