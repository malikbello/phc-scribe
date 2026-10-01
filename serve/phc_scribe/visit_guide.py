"""Visit guide (ADR-0023 §5): what to ask at an antenatal contact, what is covered, follow-ups.

Content is data (rules/visit_guide.v0.yaml), checked at load time like the rules engine:
an unknown concept, vital, test, item or source fails loudly. This module is the
reference implementation. The Takada phone app runs a TypeScript port, and the clinical
bundle (scripts/export_clinical_bundle.py) ships test vectors computed here that the port
must reproduce exactly.

Coverage is about whether a topic came up, not what the answer was: "no bleeding" covers
the bleeding question. A topic counts as covered when a concept's lexicon form or one of
the item's terms appears as a whole word in the folded transcript, or when the record
already holds the concept, vital or test.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from phc_scribe.rules import DEFAULT_ASSERTIONS, TESTS, VITALS, Facts
from phc_scribe.text import fold_text
from phc_scribe.vocab import REPO_ROOT, load_vocabulary

GUIDE_PATH = REPO_ROOT / "rules" / "visit_guide.v0.yaml"
LEXICON_PATH = REPO_ROOT / "bench" / "baselines" / "lexicon.v0.yaml"
LANGS = ("en", "yo", "pcm")


@dataclass(frozen=True)
class Item:
    id: str
    group: str
    ask_en: str
    when: str | int  # "every", "first", or the first gestational week it applies from
    concepts: tuple[str, ...]
    terms: tuple[str, ...]  # folded
    vitals: tuple[str, ...]
    tests: tuple[str, ...]
    source_ref: str
    source_section: str


@dataclass(frozen=True)
class FollowUp:
    id: str
    trigger: str
    ask: tuple[str, ...]
    why_en: str
    source_ref: str


@dataclass(frozen=True)
class Guide:
    version: str
    groups: Mapping[str, str]
    items: tuple[Item, ...]
    follow_ups: tuple[FollowUp, ...]
    concept_forms: Mapping[str, tuple[str, ...]]  # folded lexicon forms per concept

    def due(self, item: Item, first_contact: bool | None, weeks: float | None) -> bool:
        """Unknown contact number or gestational age never hides an item (safety first)."""
        if item.when == "every":
            return True
        if item.when == "first":
            return first_contact is not False
        return weeks is None or weeks >= float(item.when)

    def covered(self, item: Item, folded: str, facts: Facts) -> bool:
        if any(c in facts.findings for c in item.concepts):
            return True
        if any(v in facts.vitals for v in item.vitals) or any(t in facts.tests for t in item.tests):
            return True
        forms = [f for c in item.concepts for f in self.concept_forms.get(c, ())]
        return any(_has_word(folded, t) for t in (*forms, *item.terms))

    def status(
        self,
        transcript: str,
        facts: Facts | None = None,
        first_contact: bool | None = None,
        weeks: float | None = None,
    ) -> dict[str, Any]:
        """The guide's view of a visit so far: due items, covered or not, and follow-ups."""
        facts = facts or Facts.from_dict({})
        folded = fold_text(transcript)
        items = [
            {"id": i.id, "covered": self.covered(i, folded, facts)}
            for i in self.items
            if self.due(i, first_contact, weeks)
        ]
        covered = {i["id"] for i in items if i["covered"]}
        due = {i["id"] for i in items}
        fups = []
        for f in self.follow_ups:
            if facts.findings.get(f.trigger, frozenset()) & DEFAULT_ASSERTIONS:
                open_asks = [a for a in f.ask if a in due and a not in covered]
                if open_asks:
                    fups.append({"id": f.id, "ask": open_asks})
        return {"items": items, "follow_ups": fups}


def _has_word(folded: str, term: str) -> bool:
    return bool(term) and re.search(rf"(?<!\w){re.escape(term)}(?!\w)", folded) is not None


def _terms(raw: Mapping[str, Any] | None) -> tuple[str, ...]:
    raw = raw or {}
    unknown = set(raw) - set(LANGS)
    if unknown:
        raise ValueError(f"unknown term languages {sorted(unknown)}")
    return tuple(
        sorted({fold_text(str(t)).strip() for lang in LANGS for t in raw.get(lang) or ()} - {""})
    )


def _concept_forms(lexicon: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    return {
        c: tuple(
            sorted(
                {fold_text(str(t)).strip() for lang in ("en", "yo") for t in forms.get(lang) or ()}
            )
        )
        for c, forms in (lexicon.get("concepts") or {}).items()
    }


def parse_guide(data: Mapping[str, Any], lexicon: Mapping[str, Any]) -> Guide:
    concepts = set(load_vocabulary().ids)
    sources = set(data.get("sources") or {})
    groups = dict(data.get("groups") or {})
    items: list[Item] = []
    for raw in data["items"]:
        iid = raw["id"]
        if raw["group"] not in groups:
            raise ValueError(f"{iid}: unknown group {raw['group']!r}")
        when = raw["when"]
        if isinstance(when, Mapping):
            when = int(when["from_weeks"])
        elif when not in ("every", "first"):
            raise ValueError(f"{iid}: when must be every, first or {{from_weeks: N}}")
        cov = raw.get("covered_by") or {}
        extra = set(cov) - {"concepts", "terms", "vitals", "tests"}
        if extra:
            raise ValueError(f"{iid}: unknown covered_by keys {sorted(extra)}")
        item = Item(
            id=iid,
            group=raw["group"],
            ask_en=raw["ask_en"],
            when=when,
            concepts=tuple(cov.get("concepts") or ()),
            terms=_terms(cov.get("terms")),
            vitals=tuple(cov.get("vitals") or ()),
            tests=tuple(cov.get("tests") or ()),
            source_ref=raw["source"]["ref"],
            source_section=raw["source"].get("section", ""),
        )
        if not (item.concepts or item.terms or item.vitals or item.tests):
            raise ValueError(f"{iid}: nothing can cover this item")
        _check(iid, item.concepts, concepts, "concept")
        _check(iid, item.vitals, VITALS, "vital")
        _check(iid, item.tests, TESTS, "test")
        _check(iid, (item.source_ref,), sources, "source")
        items.append(item)
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate item ids")
    follow_ups: list[FollowUp] = []
    for raw in data.get("follow_ups") or ():
        fu = FollowUp(
            id=raw["id"],
            trigger=raw["if"],
            ask=tuple(raw["ask"]),
            why_en=raw["why_en"],
            source_ref=raw["source"]["ref"],
        )
        _check(fu.id, (fu.trigger,), concepts, "concept")
        _check(fu.id, fu.ask, set(ids), "item")
        _check(fu.id, (fu.source_ref,), sources, "source")
        follow_ups.append(fu)
    return Guide(
        version=str(data["version"]),
        groups=groups,
        items=tuple(items),
        follow_ups=tuple(follow_ups),
        concept_forms=_concept_forms(lexicon),
    )


def _check(where: str, values: Iterable[str], allowed: Iterable[str], what: str) -> None:
    unknown = sorted(set(values) - set(allowed))
    if unknown:
        raise ValueError(f"{where}: unknown {what} {unknown}")


def load_raw(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@cache
def load_guide(path: Path = GUIDE_PATH, lexicon_path: Path = LEXICON_PATH) -> Guide:
    return parse_guide(load_raw(path), load_raw(lexicon_path))


def item_ids(items: Sequence[Mapping[str, Any]], covered: bool) -> list[str]:
    return [i["id"] for i in items if i["covered"] is covered]
