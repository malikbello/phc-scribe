"""Heuristics for the Gate 1 data audit (docs/data-audit.md).

Pure functions over note text, so they are unit-tested and the audit script only
does I/O. The output is aggregate counts: no raw clinical text ever goes into the
report. The visit-type and language labels are keyword heuristics meant to size the
data, not to label it; the pilot items are still read by a human.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from bench.baselines.keyword import BP_RE, GA_RE, load_lexicon
from phc_scribe.deid import find_identifiers
from phc_scribe.text import fold_text
from phc_scribe.vocab import load_vocabulary


def _rx(*terms: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(terms) + r")\b", re.I)


VISIT_TYPES: dict[str, re.Pattern[str]] = {
    "anc": _rx(
        r"antenatal",
        r"ante-natal",
        r"anc",
        r"booking",
        r"gestation(?:al age)?",
        r"e?ga",
        r"lmp",
        r"edd",
        r"fundal height",
        r"sfh",
        r"fhr",
        r"fetal heart",
        r"foetal heart",
        r"g\d+\s*p\d+",
        r"gravida",
        r"primigravida",
        r"multigravida",
        r"\d{1,2}\s*/\s*40",
        r"weeks? pregnant",
        r"ipt(?:p)?",
        r"fefol",
    ),
    "delivery_postnatal": _rx(
        r"delivered",
        r"delivery",
        r"labou?r",
        r"postnatal",
        r"post-natal",
        r"postpartum",
        r"puerperium",
        r"svd",
        r"caesarean",
        r"c-section",
        r"apgar",
        r"episiotomy",
    ),
    "child": _rx(
        r"immuni[sz]ation",
        r"vaccin\w*",
        r"child",
        r"infant",
        r"under[- ]?5",
        r"months? old",
        r"weeks? old",
        r"growth monitoring",
        r"muac",
        r"imci",
        r"penta",
        r"bcg",
        r"opv",
    ),
    "family_planning": _rx(
        r"family planning",
        r"contracepti\w+",
        r"implant",
        r"iucd",
        r"depo",
        r"injectables?",
    ),
    "general_opd": _rx(
        r"opd",
        r"presenting complaint",
        r"complaints? of",
        r"c/o",
        r"diagnosis",
        r"impression",
        r"malaria",
        r"hypertension",
        r"diabetes",
        r"typhoid",
        r"prescribed",
        r"rx",
    ),
}

YORUBA_MARKS = re.compile(r"[ẹọṣẸỌṢ]|[̀́̄]")
YORUBA_WORDS = _rx(r"ni", r"ti", r"ko", r"kò", r"sí", r"ó", r"àti", r"mo", r"ń", r"wá", r"lọ")
HAUSA_MARKS = re.compile(r"[ɓɗƙƴƁƊƘƳ]")
HAUSA_WORDS = _rx(r"da", r"ba", r"yana", r"tana", r"ciwon", r"zazzabi", r"ciki")
IGBO_MARKS = re.compile(r"[ịụṅỊỤṄ]")
PIDGIN_WORDS = _rx(r"dey", r"wetin", r"abeg", r"una", r"pikin", r"sabi", r"na im")


def visit_types(text: str) -> list[str]:
    """Every visit type with at least one keyword hit (a note can mention several)."""
    return [name for name, rx in VISIT_TYPES.items() if rx.search(text)]


def primary_visit_type(text: str) -> str:
    """The type with the most keyword hits; ANC wins ties (it is the target scope)."""
    counts = {name: len(rx.findall(text)) for name, rx in VISIT_TYPES.items()}
    best = max(counts.values())
    if best == 0:
        return "unknown"
    winners = [n for n, c in counts.items() if c == best]
    return "anc" if "anc" in winners else winners[0]


def language_guess(text: str) -> str:
    folded = fold_text(text)
    scores = {
        "yo": len(YORUBA_MARKS.findall(text)) + 2 * len(YORUBA_WORDS.findall(text)),
        "ha": 3 * len(HAUSA_MARKS.findall(text)) + len(HAUSA_WORDS.findall(folded)),
        "ig": 3 * len(IGBO_MARKS.findall(text)),
        "pcm": 2 * len(PIDGIN_WORDS.findall(folded)),
    }
    words = max(1, len(text.split()))
    lang, score = max(scores.items(), key=lambda kv: kv[1])
    return lang if score / words >= 0.1 else "en"


def has_danger_keyword(text: str) -> bool:
    lex = load_lexicon()
    folded = fold_text(text)
    danger = load_vocabulary().danger_sign_ids
    return any(lex.concepts[c].search(folded) for c in danger if c in lex.concepts)


@dataclass
class AuditCounts:
    """Aggregates only. Safe to commit."""

    rows: int = 0
    empty_text: int = 0
    chars: list[int] = field(default_factory=list)
    words: list[int] = field(default_factory=list)
    visit_type_any: Counter[str] = field(default_factory=Counter)
    visit_type_primary: Counter[str] = field(default_factory=Counter)
    language: Counter[str] = field(default_factory=Counter)
    rows_with_identifier: Counter[str] = field(default_factory=Counter)
    rows_with_any_identifier: int = 0
    rows_with_danger_keyword: int = 0
    anc_rows_with_danger_keyword: int = 0
    rows_with_bp: int = 0
    rows_with_ga: int = 0
    exact_duplicates: int = 0
    _seen: set[int] = field(default_factory=set, repr=False)

    def add(self, text: str) -> None:
        self.rows += 1
        text = text.strip()
        if not text:
            self.empty_text += 1
            return
        key = hash(fold_text(text))
        if key in self._seen:
            self.exact_duplicates += 1
        self._seen.add(key)
        self.chars.append(len(text))
        self.words.append(len(text.split()))
        types = visit_types(text)
        self.visit_type_any.update(types or ["unknown"])
        primary = primary_visit_type(text)
        self.visit_type_primary[primary] += 1
        self.language[language_guess(text)] += 1
        kinds = {h.kind for h in find_identifiers(text)}
        self.rows_with_identifier.update(kinds)
        self.rows_with_any_identifier += bool(kinds)
        danger = has_danger_keyword(text)
        self.rows_with_danger_keyword += danger
        self.anc_rows_with_danger_keyword += danger and primary == "anc"
        self.rows_with_bp += bool(BP_RE.search(text))
        self.rows_with_ga += any(p.search(text) for p in GA_RE)

    def add_all(self, texts: Iterable[str]) -> AuditCounts:
        for t in texts:
            self.add(t)
        return self

    def summary(self) -> dict[str, object]:
        def dist(xs: list[int]) -> dict[str, float] | None:
            if not xs:
                return None
            q = statistics.quantiles(xs, n=4) if len(xs) > 1 else [xs[0]] * 3
            return {"min": min(xs), "p25": q[0], "median": q[1], "p75": q[2], "max": max(xs)}

        return {
            "rows": self.rows,
            "empty_text": self.empty_text,
            "exact_duplicates": self.exact_duplicates,
            "chars": dist(self.chars),
            "words": dist(self.words),
            "visit_type_primary": dict(self.visit_type_primary.most_common()),
            "visit_type_any": dict(self.visit_type_any.most_common()),
            "language_guess": dict(self.language.most_common()),
            "rows_with_identifier": dict(self.rows_with_identifier.most_common()),
            "rows_with_any_identifier": self.rows_with_any_identifier,
            "rows_with_danger_keyword": self.rows_with_danger_keyword,
            "anc_rows_with_danger_keyword": self.anc_rows_with_danger_keyword,
            "rows_with_bp": self.rows_with_bp,
            "rows_with_ga": self.rows_with_ga,
        }


# ------------------------------------------------------------ dataset card

CARD_TOPICS: dict[str, re.Pattern[str]] = {
    "license": _rx(r"licen[cs]e", r"cc[- ]by\S*", r"creative commons"),
    "consent": _rx(r"consent\w*"),
    "ethics": _rx(r"ethic\w*", r"irb", r"nhrec", r"institutional review", r"approval"),
    "deidentification": _rx(
        r"de-?identif\w*", r"anonymi[sz]\w*", r"pseudonymi[sz]\w*", r"redact\w*"
    ),
    "provenance": _rx(r"hospital", r"clinic", r"collected", r"source", r"handwritten", r"ocr"),
}


def card_topics(card: str) -> dict[str, int]:
    """How often each governance topic is mentioned in the dataset card."""
    return {topic: len(rx.findall(card)) for topic, rx in CARD_TOPICS.items()}
