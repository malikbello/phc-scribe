"""Test-set freeze and train/test separation (docs/eval-plan.md "Freezing"; ADR-0022).

The freeze has two stages (ADR-0022):

1. **Items** (`freeze_items`): for every test file, the SHA-256 of its *items* (id, group,
   language, transcript; never gold labels or hints) and their count. This fixes which
   items and speakers are test data, so training data can be built against it while the
   labels are still being made. Works on benchmark files (BenchItem) and label queues
   (QueueItem) alike.
2. **Labels** (`freeze_labels`): before any fine-tuned model is scored, each file is
   replaced by its labelled version (which must hold exactly the same items) and the
   whole file is hashed. Gold labels can't change after that.

Training data may only be built against a manifest whose items still match their
hashes, and no training example may share a group with, duplicate or nearly duplicate
a test item (folded-text hash, then word 8-gram overlap).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from bench.items import BenchItem, read_jsonl
from phc_scribe.text import fold_text

SHINGLE = 8
NEAR_DUP = 0.5  # share of a training text's 8-grams found in one test item
ITEM_FIELDS = ("item_id", "group_id", "language", "transcript")


class TestItem(BaseModel):
    """What stage 1 fixes about a test item: identity, speaker group and text."""

    model_config = ConfigDict(extra="ignore")
    item_id: str
    group_id: str
    language: str
    transcript: str


class FrozenFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    items: int
    items_sha256: str  # stage-1 items; never changes
    sha256: str | None = None  # whole labelled file; set at stage 2
    frozen_as: str | None = None  # stage-1 path, when stage 2 swapped in a labelled file
    excluded: list[str] = []  # stage-1 item ids adjudicated unlabellable, dropped at stage 2


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal[1, 2]
    frozen_at: str
    labels_frozen_at: str | None = None
    files: list[FrozenFile]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def read_test_items(path: Path) -> list[TestItem]:
    return [
        TestItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def items_sha256(items: Sequence[TestItem]) -> str:
    """Order-independent hash of the stage-1 fields; refuses duplicate item ids."""
    ids = [i.item_id for i in items]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate item_id in a test file")
    lines = sorted(
        json.dumps([getattr(i, f) for f in ITEM_FIELDS], ensure_ascii=False) for i in items
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def freeze_items(paths: Sequence[Path], root: Path) -> Manifest:
    """Stage 1: fix the test items (no labels needed)."""
    files = []
    for p in paths:
        items = read_test_items(p)
        files.append(
            FrozenFile(path=_rel(p, root), items=len(items), items_sha256=items_sha256(items))
        )
    return Manifest(stage=1, frozen_at=_now(), files=files)


def freeze_labels(
    manifest: Manifest,
    root: Path,
    labelled: Mapping[str, Path] | None = None,
    excluded: Mapping[str, Sequence[str]] | None = None,
) -> Manifest:
    """Stage 2: hash the labelled files.

    `labelled` maps a stage-1 path to the gold-labelled benchmark file that replaces it
    (a label queue -> its adjudicated BenchItems); unmapped files are hashed in place.
    `excluded` lists, per stage-1 path, item ids adjudicated unlabellable (garbled, cut
    off): they are the only items allowed to be missing, and they are recorded. The
    stage-1 file must still hold its frozen items, and the labelled file exactly those
    items minus the exclusions.
    """
    if manifest.stage != 1:
        raise ValueError(f"labels already frozen ({manifest.labels_frozen_at})")
    labelled, excluded = dict(labelled or {}), dict(excluded or {})
    unknown = (set(labelled) | set(excluded)) - {f.path for f in manifest.files}
    if unknown:
        raise ValueError(f"not in the stage-1 manifest: {sorted(unknown)}")
    files = []
    for f in manifest.files:
        frozen = read_test_items(root / f.path)
        if items_sha256(frozen) != f.items_sha256:
            raise ValueError(
                f"{f.path}: test items changed since the freeze ({manifest.frozen_at})"
            )
        drop = set(excluded.get(f.path, ()))
        stray = drop - {i.item_id for i in frozen}
        if stray:
            raise ValueError(f"{f.path}: excluded ids not in the file: {sorted(stray)}")
        path = labelled.get(f.path, root / f.path)
        expected = [i for i in frozen if i.item_id not in drop]
        if items_sha256(read_test_items(path)) != items_sha256(expected):
            raise ValueError(f"{path} does not hold the items frozen as {f.path}")
        sum(1 for _ in read_jsonl(path, BenchItem))  # must be gold-labelled benchmark items
        rel = _rel(path, root)
        files.append(
            FrozenFile(
                path=rel,
                items=len(expected),
                items_sha256=f.items_sha256,
                sha256=sha256(path),
                frozen_as=f.path if rel != f.path else None,
                excluded=sorted(drop),
            )
        )
    return manifest.model_copy(update={"stage": 2, "labels_frozen_at": _now(), "files": files})


def load_manifest(manifest_path: Path) -> Manifest:
    return Manifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))


def load_frozen_items(manifest_path: Path, root: Path) -> list[TestItem]:
    """Test items from a manifest (either stage); refuses if any item changed."""
    manifest = load_manifest(manifest_path)
    out: list[TestItem] = []
    for f in manifest.files:
        items = read_test_items(root / f.path)
        changed = (
            sha256(root / f.path) != f.sha256 if f.sha256 else items_sha256(items) != f.items_sha256
        )
        if changed:
            raise ValueError(
                f"{f.path}: test items changed since the freeze ({manifest.frozen_at})"
            )
        out.extend(items)
    return out


def load_gold_items(manifest_path: Path, root: Path) -> list[BenchItem]:
    """Gold-labelled test items; only after stage 2, and only if no file changed."""
    manifest = load_manifest(manifest_path)
    if manifest.stage != 2:
        raise ValueError("labels are not frozen yet (ADR-0022 stage 2)")
    out: list[BenchItem] = []
    for f in manifest.files:
        path = root / f.path
        if sha256(path) != f.sha256:
            raise ValueError(
                f"{f.path} changed since the labels were frozen ({manifest.labels_frozen_at})"
            )
        out.extend(read_jsonl(path, BenchItem))
    return out


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
