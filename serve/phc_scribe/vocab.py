"""Loads the controlled finding vocabulary (schema/vocab/*.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VOCAB_PATH = REPO_ROOT / "schema" / "vocab" / "anc_concepts.v0.1.yaml"


@dataclass(frozen=True)
class Concept:
    id: str
    label_en: str
    danger_sign: bool
    definition: str
    dak: str | None
    dak_verified: bool


@dataclass(frozen=True)
class Vocabulary:
    version: str
    module: str
    concepts: tuple[Concept, ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(c.id for c in self.concepts)

    @property
    def danger_sign_ids(self) -> frozenset[str]:
        return frozenset(c.id for c in self.concepts if c.danger_sign)

    def get(self, concept_id: str) -> Concept:
        for c in self.concepts:
            if c.id == concept_id:
                return c
        raise KeyError(concept_id)


def parse_vocabulary(data: dict) -> Vocabulary:
    concepts = tuple(
        Concept(
            id=c["id"],
            label_en=c["label_en"],
            danger_sign=bool(c["danger_sign"]),
            definition=c["definition"],
            dak=c.get("dak"),
            dak_verified=bool(c.get("dak_verified", False)),
        )
        for c in data["concepts"]
    )
    ids = [c.id for c in concepts]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate concept ids: {duplicates}")
    return Vocabulary(version=str(data["version"]), module=data["module"], concepts=concepts)


@cache
def load_vocabulary(path: Path = VOCAB_PATH) -> Vocabulary:
    with path.open(encoding="utf-8") as f:
        return parse_vocabulary(yaml.safe_load(f))
