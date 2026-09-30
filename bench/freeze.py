"""Test-set freeze and train/test separation (docs/eval-plan.md, "Freezing").

A freeze manifest records the SHA-256 of every test file. Training data may only be
built against a frozen test set whose files still match their hashes, and no training
example may duplicate or nearly duplicate a test item (folded-text hash, then word
8-gram overlap).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from bench.items import BenchItem, read_jsonl
from phc_scribe.text import fold_text

SHINGLE = 8
NEAR_DUP = 0.5  # share of a training text's 8-grams found in one test item


class FrozenFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    sha256: str
    items: int


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frozen_at: str
    files: list[FrozenFile]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(paths: Sequence[Path], root: Path) -> Manifest:
    files = [
        FrozenFile(
            path=p.resolve().relative_to(root.resolve()).as_posix(),
            sha256=sha256(p),
            items=sum(1 for _ in read_jsonl(p, BenchItem)),
        )
        for p in paths
    ]
    return Manifest(frozen_at=datetime.now(UTC).isoformat(timespec="seconds"), files=files)


def load_frozen_items(manifest_path: Path, root: Path) -> list[BenchItem]:
    """Test items from a manifest; refuses if any file changed since the freeze."""
    manifest = Manifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))
    items: list[BenchItem] = []
    for f in manifest.files:
        path = root / f.path
        if sha256(path) != f.sha256:
            raise ValueError(f"{f.path} changed since the freeze ({manifest.frozen_at})")
        items.extend(read_jsonl(path, BenchItem))
    return items


def _words(text: str) -> list[str]:
    return fold_text(text).lower().split()


def _shingles(text: str) -> set[tuple[str, ...]]:
    w = _words(text)
    return {tuple(w[i : i + SHINGLE]) for i in range(max(1, len(w) - SHINGLE + 1))}


class Overlap:
    """Index of test texts for exact and near-duplicate checks."""

    def __init__(self, test_texts: Iterable[str]):
        self.exact: set[str] = set()
        self.index: dict[tuple[str, ...], set[int]] = {}
        for n, text in enumerate(test_texts):
            self.exact.add(" ".join(_words(text)))
            for sh in _shingles(text):
                self.index.setdefault(sh, set()).add(n)

    def reason(self, text: str) -> str | None:
        """Why this text may not be used for training, or None if it is clean."""
        if " ".join(_words(text)) in self.exact:
            return "exact duplicate of a test item"
        shingles = _shingles(text)
        hits: dict[int, int] = {}
        for sh in shingles:
            for n in self.index.get(sh, ()):
                hits[n] = hits.get(n, 0) + 1
        if hits and max(hits.values()) / len(shingles) >= NEAR_DUP:
            return "near duplicate of a test item"
        return None
