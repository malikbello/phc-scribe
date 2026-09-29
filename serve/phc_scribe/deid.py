"""Rule-based identifier detection and scrubbing (v0).

Used by the data audit (counts only) and before any real note enters a benchmark.
This is a first pass, not a guarantee: every test item still gets a manual check
(docs/architecture.md, section 5). Patterns target Nigerian formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PATTERNS: dict[str, re.Pattern[str]] = {
    # +234 803 123 4567 / 0803-123-4567 / 08031234567
    "phone": re.compile(r"(?<!\d)(?:\+?234[\s-]?|0)[789][01]\d(?:[\s-]?\d){7}(?!\d)"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "date": re.compile(
        r"\b\d{1,2}[/.-]\d{1,2}[/.-](?:19|20)?\d{2}\b"
        r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"[a-z]*\.?,?\s+(?:19|20)\d{2}\b",
        re.I,
    ),
    "record_number": re.compile(
        r"\b(?:hosp(?:ital)?|folder|card|reg(?:istration)?|file|mrn|anc|patient)\s*"
        r"(?:no|number|num|#)\.?\s*[:.]?\s*[A-Z0-9][A-Z0-9/-]{2,}",
        re.I,
    ),
    "labelled_name": re.compile(
        r"\b(?i:name|patient|client|husband|mrs|mr|miss|madam|mama|iya|baba)\b[:.]?\s+"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
    ),
    "address": re.compile(
        r"\b\d{1,4},?\s+(?:[A-Z][a-z]+\s+){1,3}"
        r"(?:street|st|road|rd|close|avenue|ave|crescent|layout|estate|lane)\b",
        re.I,
    ),
    "nin_or_bvn": re.compile(r"(?<!\d)\d{11}(?!\d)"),
}


@dataclass(frozen=True)
class Hit:
    kind: str
    start: int
    end: int


def find_identifiers(text: str) -> list[Hit]:
    hits = [Hit(kind, m.start(), m.end()) for kind, p in PATTERNS.items() for m in p.finditer(text)]
    return sorted(hits, key=lambda h: (h.start, -(h.end - h.start)))


def scrub(text: str) -> str:
    """Replace detected identifiers with ``[KIND]`` placeholders (overlaps merged)."""
    out: list[str] = []
    pos = 0
    for hit in find_identifiers(text):
        if hit.start < pos:
            continue
        out.append(text[pos : hit.start])
        out.append(f"[{hit.kind.upper()}]")
        pos = hit.end
    out.append(text[pos:])
    return "".join(out)
