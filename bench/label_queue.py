"""Label queue for real patient-speech items (stratum S4, ADR-0016).

Pure functions so they are unit-tested; the scripts only do I/O.

    source rows ──sample_queue──▶ QueueItem JSONL ──labeler.html──▶ Label JSONL
                                                                        │
                        QueueItem + Label ──build_items──▶ BenchItem JSONL (gold)

Keyword-baseline hints travel with each queue item so the labeler can show them. They
are suggestions only: the tool never pre-ticks them, and the report discloses that
annotators could see them.
"""

from __future__ import annotations

import random
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bench.items import BenchItem, Language, Stratum
from phc_scribe.encounter import Encounter, Finding
from phc_scribe.grounding import locate
from phc_scribe.text import fold_text

# NigBench-MAMAI config names -> our language codes. Kanuri, Nupe and Fulfulde are out
# of scope for v0 (no reviewer on the team reads them).
MAMAI_LANGUAGES: dict[str, Language] = {
    "Yoruba": "yo",
    "Pidgin": "pcm",
    "Hausa": "ha",
    "Igbo": "ig",
}

SkipReason = Literal[
    "not_pregnancy_related",
    "unintelligible",
    "not_patient_report",
    "duplicate",
    "other",
]


class SourceRow(BaseModel):
    """One utterance from a source dataset (text columns only; audio stays remote)."""

    model_config = ConfigDict(extra="ignore")

    source: str
    source_id: str
    speaker_id: str
    language: Language
    split: str
    transcript: str
    audio_duration: float | None = None


class QueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    group_id: str = Field(description="Speaker id: all of a speaker's items stay in one split.")
    language: Language
    source: str
    source_id: str
    transcript: str
    hints: list[Finding] = Field(default_factory=list)
    sampling: Literal["enriched", "random"] | None = Field(
        default=None,
        description="Sampling group under ADR-0018 (WazobiaSpeech); None for MAMAI queues.",
    )


class Label(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    status: Literal["labelled", "skip"]
    skip_reason: SkipReason | None = None
    findings: list[Finding] = Field(default_factory=list)
    labeller: str
    labelled_at: str
    note: str | None = None
    elapsed_ms: int | None = None


def sample_queue(
    rows: Iterable[SourceRow],
    per_language: Mapping[str, int],
    seed: int,
    hint_fn=None,
) -> list[QueueItem]:
    """Seeded random sample, stratified by language. Empty transcripts are dropped.

    Deterministic for a given seed and input order-independent (rows are sorted by
    source_id before shuffling), so the queue can be rebuilt and audited.
    """
    by_lang: dict[str, list[SourceRow]] = defaultdict(list)
    for r in rows:
        if r.transcript.strip():
            by_lang[r.language].append(r)
    rng = random.Random(seed)  # noqa: S311 (sampling, not security)
    queue: list[QueueItem] = []
    for lang in sorted(per_language):
        pool = sorted(by_lang.get(lang, []), key=lambda r: r.source_id)
        rng.shuffle(pool)
        for r in pool[: per_language[lang]]:
            hints = hint_fn(r.transcript) if hint_fn else []
            queue.append(
                QueueItem(
                    item_id=f"s4-{lang}-{r.source_id}",
                    group_id=f"{r.source}:{r.speaker_id}",
                    language=r.language,
                    source=r.source,
                    source_id=r.source_id,
                    transcript=r.transcript,
                    hints=hints,
                )
            )
    return queue


# ADR-0018 enrichment terms, fixed before any sampling. Matched as whole words on
# diacritic-folded, lower-cased text, so Yoruba tone marks and under-dots don't matter.
# A clip matching any term goes to the "enriched" group; the rest are "random".
ENRICH_TERMS: tuple[str, ...] = (
    # pregnancy and antenatal care (English / Pidgin)
    "pregnant",
    "pregnancy",
    "antenatal",
    "belle",
    "pikin",
    "born",
    "midwife",
    "labour",
    "labor",
    "miscarriage",
    "baby",
    # pregnancy and antenatal care (Yoruba, folded)
    "oyun",
    "aboyun",
    "loyun",
    "ibimo",
    "bimo",
    "omo inu",
    "agbebi",
    # danger-sign vocabulary (English / Pidgin)
    "bleeding",
    "bleed",
    "blood",
    "headache",
    "convulsion",
    "fit",
    "swelling",
    "swell",
    "fever",
    "blurred",
    "dizzy",
    "breath",
    "water break",
    # danger-sign vocabulary (Yoruba, folded)
    "eje",
    "ori fifo",
    "giri",
    "wiwu",
    "iba",
    "oju",
    "ese wiwu",
)
_ENRICH_RE = re.compile(r"\b(?:" + "|".join(re.escape(t) for t in ENRICH_TERMS) + r")\b")


def enriched(transcript: str) -> bool:
    """True when a transcript matches an ADR-0018 enrichment term."""
    return bool(_ENRICH_RE.search(fold_text(transcript).lower()))


def sample_enriched_queue(
    rows: Iterable[SourceRow],
    per_language: Mapping[str, int],
    enriched_share: float,
    seed: int,
    hint_fn=None,
    prefix: str = "s4w",
) -> list[QueueItem]:
    """ADR-0018 sampling: per language, an enriched group and a random group.

    `enriched_share` of each language's quota comes from clips matching ENRICH_TERMS
    and the rest from the remaining clips, each a seeded simple random sample. If a
    group is short, the other group fills the gap, so the language quota still holds.
    Deterministic and input-order independent, like sample_queue.
    """
    groups: dict[tuple[str, bool], list[SourceRow]] = defaultdict(list)
    for r in rows:
        if r.transcript.strip():
            groups[(r.language, enriched(r.transcript))].append(r)
    rng = random.Random(seed)  # noqa: S311 (sampling, not security)
    queue: list[QueueItem] = []
    for lang in sorted(per_language):
        pools = {}
        for is_enriched in (True, False):
            pool = sorted(groups.get((lang, is_enriched), []), key=lambda r: r.source_id)
            rng.shuffle(pool)
            pools[is_enriched] = pool
        want_e = min(round(per_language[lang] * enriched_share), len(pools[True]))
        want_r = min(per_language[lang] - want_e, len(pools[False]))
        want_e = min(per_language[lang] - want_r, len(pools[True]))
        for is_enriched, n in ((True, want_e), (False, want_r)):
            for r in pools[is_enriched][:n]:
                queue.append(
                    QueueItem(
                        item_id=f"{prefix}-{lang}-{r.source_id}",
                        group_id=f"{r.source}:{r.speaker_id}",
                        language=r.language,
                        source=r.source,
                        source_id=r.source_id,
                        transcript=r.transcript,
                        hints=hint_fn(r.transcript) if hint_fn else [],
                        sampling="enriched" if is_enriched else "random",
                    )
                )
    return queue


def keyword_hints(transcript: str) -> list[Finding]:
    """Findings from the rung-1 keyword baseline, used only as labeler hints."""
    from bench.baselines.keyword import extract

    return list(extract(transcript).findings)


class BuildReport(BaseModel):
    items: int = 0
    skipped: int = 0
    unlabelled: int = 0
    skipped_ids: list[str] = Field(default_factory=list)  # for freeze --exclude (ADR-0022)
    unlabelled_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def build_items(
    queue: Sequence[QueueItem],
    labels: Iterable[Label],
    stratum: Stratum = "S4",
) -> tuple[list[BenchItem], BuildReport]:
    """Join queue items with their latest label into gold benchmark items.

    Every evidence quote must occur verbatim (after NFC normalisation) in the
    transcript; items that fail are reported, not silently fixed.
    """
    latest: dict[str, Label] = {}
    for lab in labels:
        prev = latest.get(lab.item_id)
        if prev is None or lab.labelled_at >= prev.labelled_at:
            latest[lab.item_id] = lab
    report = BuildReport()
    known = {q.item_id for q in queue}
    for item_id in sorted(set(latest) - known):
        report.errors.append(f"{item_id}: label for an item not in the queue")
    items: list[BenchItem] = []
    for q in queue:
        lab = latest.get(q.item_id)
        if lab is None:
            report.unlabelled += 1
            report.unlabelled_ids.append(q.item_id)
            continue
        if lab.status == "skip":
            report.skipped += 1
            report.skipped_ids.append(q.item_id)
            continue
        bad = [
            f.concept
            for f in lab.findings
            if f.evidence is not None and locate(q.transcript, f.evidence.text) is None
        ]
        if bad:
            report.errors.append(f"{q.item_id}: evidence not found verbatim for {bad}")
            continue
        try:
            gold = Encounter(findings=lab.findings)
        except ValueError as e:
            report.errors.append(f"{q.item_id}: {str(e).splitlines()[0]}")
            continue
        items.append(
            BenchItem(
                item_id=q.item_id,
                group_id=q.group_id,
                stratum=stratum,
                language=q.language,
                origin="real",
                transcript=q.transcript,
                gold=gold,
            )
        )
        report.items += 1
    return items, report
