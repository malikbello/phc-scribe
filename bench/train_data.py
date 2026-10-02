"""Training-data rules from ADR-0024, stage 0. Pure functions: no model, no network.

- `audit_teacher`: removes findings the ontology says a speaker cannot produce.
  `looks_very_ill` is defined as the health worker stating it (schema/vocab), so a
  teacher label of it on patient or general speech is wrong by definition.
- `concept_precision` / `concepts_to_drop`: per-concept check of teacher labels against
  the blind 50-clip check; a concept the teacher gets wrong too often is dropped.
- `drop_items_with`: removes whole items carrying a dropped concept (rather than turning
  them into false "no finding" examples).
- `split_by_group`: a deterministic dev split by speaker/group, so every recipe choice
  is made on dev data and never on the test set.
- `load_phrasebank`: the clinician- and native-speaker-approved rare-danger-sign items,
  refused until both approvals are recorded.
- `cap_share`: limits the share of constructed items in the training mix.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterable, Sequence
from pathlib import Path

import yaml
from pydantic import BaseModel

from bench.items import BenchItem
from phc_scribe.encounter import Encounter
from phc_scribe.grounding import ground

# Concepts the vocabulary defines by what the health worker says, so they cannot come
# from a patient's or a general speaker's own speech (teacher sources are WazobiaSpeech).
HEALTH_WORKER_ONLY = frozenset({"looks_very_ill"})
POSITIVE = frozenset({"present", "possible"})
SEED = 20261008


class AuditReport(BaseModel):
    items: int = 0
    findings_removed: int = 0
    items_changed: int = 0
    became_empty: int = 0
    empty_over_cap: int = 0
    kept: int = 0


def audit_teacher(
    items: Sequence[BenchItem], empty_cap: float = 0.5, seed: int = SEED
) -> tuple[list[BenchItem], AuditReport]:
    """Remove health-worker-only findings from teacher-labelled items, then re-apply the cap
    on items with no finding (ADR-0021: at most half of the teacher set)."""
    report = AuditReport(items=len(items))
    full: list[BenchItem] = []
    empty: list[BenchItem] = []
    for item in items:
        findings = item.gold.findings
        kept = [f for f in findings if str(f.concept) not in HEALTH_WORKER_ONLY]
        if len(kept) != len(findings):
            report.findings_removed += len(findings) - len(kept)
            report.items_changed += 1
            report.became_empty += int(not kept)
            gold = item.gold.model_copy(update={"findings": kept})
            item = item.model_copy(update={"gold": gold})
        (full if item.gold.findings else empty).append(item)
    allowed = int(len(full) * empty_cap / (1 - empty_cap)) if empty_cap < 1 else len(empty)
    rng = random.Random(seed)  # noqa: S311 (sampling, not security)
    empty = sorted(empty, key=lambda i: i.item_id)
    rng.shuffle(empty)
    report.empty_over_cap = max(0, len(empty) - allowed)
    out = sorted(full + empty[:allowed], key=lambda i: i.item_id)
    report.kept = len(out)
    return out, report


def positives(record: Encounter) -> set[str]:
    return {str(f.concept) for f in record.findings if str(f.assertion) in POSITIVE}


def concept_precision(
    pairs: Iterable[tuple[Encounter, set[str]]],
) -> dict[str, dict[str, int | float | None]]:
    """Per concept: of the clips where the teacher said present/possible, how many the human
    checker confirmed. `pairs` are (teacher record, concepts the checker marked positive)."""
    stats: dict[str, dict[str, int]] = {}
    for teacher, human in pairs:
        for c in positives(teacher):
            s = stats.setdefault(c, {"teacher_positive": 0, "confirmed": 0})
            s["teacher_positive"] += 1
            s["confirmed"] += int(c in human)
    return {
        c: {
            **s,
            "precision": s["confirmed"] / s["teacher_positive"] if s["teacher_positive"] else None,
        }
        for c, s in sorted(stats.items())
    }


def concepts_to_drop(
    precision: dict[str, dict[str, int | float | None]], floor: float = 0.8, min_support: int = 3
) -> list[str]:
    """Concepts with at least `min_support` teacher positives in the check and precision below
    `floor` (ADR-0024). Fewer than `min_support` is too little evidence either way."""
    out = []
    for c, s in precision.items():
        p, n = s["precision"], s["teacher_positive"]
        if p is not None and isinstance(n, int) and n >= min_support and p < floor:
            out.append(c)
    return out


def drop_items_with(items: Sequence[BenchItem], concepts: Iterable[str]) -> list[BenchItem]:
    bad = set(concepts)
    return [i for i in items if not (positives(i.gold) & bad)]


def _bucket(group_id: str, seed: int) -> float:
    h = hashlib.sha256(f"{seed}:{group_id}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def split_by_group(
    items: Sequence[BenchItem], dev_frac: float = 0.15, seed: int = SEED
) -> tuple[list[BenchItem], list[BenchItem]]:
    """(train, dev). A group (speaker, source note) lands wholly on one side, chosen by a
    seeded hash of its id, so the split is stable when items are added or removed."""
    train, dev = [], []
    for item in items:
        (dev if _bucket(item.group_id, seed) < dev_frac else train).append(item)
    return train, dev


class PhrasebankError(ValueError):
    pass


def load_phrasebank(path: Path) -> list[BenchItem]:
    """Constructed rare-danger-sign items (ADR-0024 stage 0). Refused unless the file records
    both approvals: the native-speaker check of the language and the clinical check."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    approvals = doc.get("approved_by") or {}
    missing = [k for k in ("language", "clinical") if not approvals.get(k)]
    if missing:
        raise PhrasebankError(f"{path.name}: not approved yet ({', '.join(missing)})")
    items = []
    for e in doc.get("entries", []):
        finding = {
            "concept": e["concept"],
            "assertion": e["assertion"],
            "evidence": {"text": e["evidence"]},
        }
        record = Encounter.model_validate({"findings": [finding]})
        g = ground(record, e["text"])
        if g.dropped or g.folded_matches:
            raise PhrasebankError(f"{e['id']}: evidence is not a verbatim quote of the text")
        items.append(
            BenchItem(
                item_id=f"p-{e['id']}",
                group_id=f"phrasebank:{e['id']}",
                stratum="P",
                language=e["language"],
                origin="constructed",
                transcript=e["text"],
                gold=g.record,
            )
        )
    return items


def cap_share(
    main: Sequence[BenchItem], extra: Sequence[BenchItem], share: float, seed: int = SEED
) -> list[BenchItem]:
    """At most `share` of the combined set comes from `extra` (seeded, stable)."""
    allowed = int(len(main) * share / (1 - share)) if share < 1 else len(extra)
    pool = sorted(extra, key=lambda i: i.item_id)
    random.Random(seed).shuffle(pool)  # noqa: S311 (sampling, not security)
    return pool[:allowed]
