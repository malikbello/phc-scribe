"""Rung 1 of the baseline ladder: a rules/keyword extractor with no ML.

It answers "how far do keywords and regexes get?". Every model rung has to beat it.
Findings come from lexicon matches on folded text, with NegEx-style assertion cues;
vitals, ANC fields and tests come from regexes over note shorthand (BP 120/80,
GA 32/40, G3P2, PCV 30%, TCA 2/52).
"""

from __future__ import annotations

import datetime as dt
import itertools
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from phc_scribe.encounter import (
    Anc,
    Assertion,
    BloodPressure,
    Count,
    Disposition,
    Encounter,
    Evidence,
    Finding,
    GestationalAge,
    LabTest,
    Medication,
    MedicationGiven,
    NextVisit,
    Pulse,
    Referral,
    Temperature,
    TestResult,
    Vitals,
    Weight,
)
from phc_scribe.text import Folded, fold, fold_text, normalise
from phc_scribe.vocab import load_vocabulary

LEXICON_PATH = Path(__file__).with_name("lexicon.v0.yaml")
SYSTEM_NAME = "rung1-keyword-v0"


def _alternation(terms: Iterable[str]) -> str:
    folded = sorted({fold_text(t).strip() for t in terms if t.strip()}, key=len, reverse=True)
    return "|".join(re.escape(t) for t in folded)


def _word_regex(terms: Iterable[str]) -> re.Pattern[str] | None:
    alt = _alternation(terms)
    return re.compile(rf"(?<![\w]){'(?:' + alt + ')'}(?![\w])") if alt else None


@dataclass(frozen=True)
class Lexicon:
    concepts: dict[str, re.Pattern[str]]
    neg_pre: re.Pattern[str]
    neg_post: re.Pattern[str]
    hedge_pre: re.Pattern[str]
    hedge_post: re.Pattern[str]
    historical: re.Pattern[str]
    answer_yes: re.Pattern[str]
    answer_no: re.Pattern[str]
    clause_break: re.Pattern[str]
    medications: dict[Medication, re.Pattern[str]]


def _required(pattern: re.Pattern[str] | None, what: str) -> re.Pattern[str]:
    if pattern is None:
        raise ValueError(f"lexicon: {what} is empty")
    return pattern


def parse_lexicon(data: dict[str, Any]) -> Lexicon:
    unknown = set(data["concepts"]) - set(load_vocabulary().ids)
    if unknown:
        raise ValueError(f"lexicon: unknown concepts {sorted(unknown)}")
    concepts: dict[str, re.Pattern[str]] = {}
    for concept, forms in data["concepts"].items():
        pattern = _word_regex([*(forms.get("en") or []), *(forms.get("yo") or [])])
        if pattern is not None:
            concepts[concept] = pattern
    cues = data["cues"]
    answer_yes = _required(_word_regex(cues["answer_yes"]), "answer_yes")
    answer_no = _required(_word_regex(cues["answer_no"]), "answer_no")
    return Lexicon(
        concepts=concepts,
        neg_pre=_required(_word_regex(cues["negation"]["pre"]), "negation.pre"),
        neg_post=re.compile(rf"^\W*(?:{_alternation(cues['negation']['post'])})(?![\w])"),
        hedge_pre=_required(_word_regex(cues["hedge"]["pre"]), "hedge.pre"),
        hedge_post=re.compile(rf"^\W*(?:{_alternation(cues['hedge']['post'])})(?![\w])"),
        historical=_required(_word_regex(cues["historical"]["any"]), "historical"),
        answer_yes=re.compile(rf"^\W*(?:{answer_yes.pattern})"),
        answer_no=re.compile(rf"^\W*(?:{answer_no.pattern})"),
        clause_break=_required(_word_regex(cues["clause_breaks"]), "clause_breaks"),
        medications={
            Medication(k): _required(_word_regex(v), f"medications.{k}")
            for k, v in data["medications"].items()
        },
    )


@cache
def load_lexicon(path: Path = LEXICON_PATH) -> Lexicon:
    with path.open(encoding="utf-8") as f:
        return parse_lexicon(yaml.safe_load(f))


# ------------------------------------------------------------------ clauses


@dataclass(frozen=True)
class Clause:
    start: int  # offsets in folded text
    end: int
    is_question: bool


def _clauses(folded: str, lex: Lexicon) -> list[Clause]:
    bounds = [0]
    for m in re.finditer(r"[.;!?\n]+", folded):
        bounds.append(m.end())
    for m in lex.clause_break.finditer(folded):
        bounds.append(m.start())
    bounds = sorted(set(bounds) | {len(folded)})
    out: list[Clause] = []
    for s, e in itertools.pairwise(bounds):
        if folded[s:e].strip():
            out.append(Clause(s, e, "?" in folded[s:e]))
    return out


def _clause_at(clauses: list[Clause], pos: int) -> int:
    for i, c in enumerate(clauses):
        if c.start <= pos < c.end:
            return i
    return len(clauses) - 1


# ----------------------------------------------------------------- findings


@dataclass(frozen=True)
class _Match:
    concept: str
    start: int  # folded offsets
    end: int


def _term_matches(folded: str, lex: Lexicon) -> list[_Match]:
    raw = [
        _Match(concept, m.start(), m.end())
        for concept, pattern in lex.concepts.items()
        for m in pattern.finditer(folded)
    ]
    # Longest match wins: "severe headache" hides the "headache" inside it.
    raw.sort(key=lambda m: (m.start, -(m.end - m.start)))
    kept: list[_Match] = []
    for m in raw:
        if any(k.start <= m.start and m.end <= k.end for k in kept):
            continue
        kept.append(m)
    return kept


def _assertion(folded: str, m: _Match, clauses: list[Clause], lex: Lexicon) -> Assertion | None:
    ci = _clause_at(clauses, m.start)
    clause = clauses[ci]
    pre = folded[clause.start : m.start]
    pre = pre[pre.rfind(",") + 1 :]
    post = folded[m.end : clause.end]
    clause_text = folded[clause.start : clause.end]

    if clause.is_question:
        # "Any bleeding? No." The answer is in the next clause; no answer, no finding.
        nxt = folded[clauses[ci + 1].start : clauses[ci + 1].end] if ci + 1 < len(clauses) else ""
        if lex.answer_no.search(nxt):
            return Assertion.absent
        if lex.answer_yes.search(nxt):
            return Assertion.present
        return None
    if lex.neg_pre.search(pre) or lex.neg_post.search(post):
        return Assertion.absent
    if lex.historical.search(clause_text):
        return Assertion.historical
    if lex.hedge_pre.search(pre) or lex.hedge_post.search(post):
        return Assertion.possible
    return Assertion.present


def _evidence(ft: Folded, start: int, end: int) -> Evidence:
    s, e = ft.to_source_span(start, end)
    return Evidence(text=ft.source[s:e], start=s, end=e)


def extract_findings(ft: Folded, lex: Lexicon) -> list[Finding]:
    clauses = _clauses(ft.text, lex)
    seen: set[tuple[str, Assertion]] = set()
    findings: list[Finding] = []
    for m in _term_matches(ft.text, lex):
        assertion = _assertion(ft.text, m, clauses, lex)
        if assertion is None or (m.concept, assertion) in seen:
            continue
        seen.add((m.concept, assertion))
        findings.append(
            Finding(
                concept=m.concept,  # pyright: ignore[reportArgumentType]
                assertion=assertion,
                evidence=_evidence(ft, m.start, m.end),
            )
        )
    return findings


# ------------------------------------------------------- numbers (source text)

_SEP = r"\s*(?:is|was|of|at|:|=|-)?\s*"
_NUM = r"(\d{1,3}(?:[.,]\d+)?)"
BP_RE = re.compile(r"(?<![\d/])(\d{2,3})\s*(?:/|over)\s*(\d{2,3})(?![\d/])", re.I)
TEMP_RE = [
    re.compile(rf"\btemp(?:erature)?{_SEP}{_NUM}", re.I),
    re.compile(rf"(?<![\d.]){_NUM}\s*(?:°\s*c\b|℃|degrees?\b|deg\b)", re.I),
]
WEIGHT_RE = [
    re.compile(rf"(?<![\d.]){_NUM}\s*(?:kg|kgs|kilo(?:gram)?s?)\b", re.I),
    re.compile(rf"\bweight{_SEP}{_NUM}", re.I),
]
PULSE_RE = [
    re.compile(rf"\b(?:pulse(?: rate)?|pr|hr|heart rate){_SEP}(\d{{2,3}})", re.I),
    re.compile(r"(?<![\d.])(\d{2,3})\s*(?:bpm|b/min|beats per minute)", re.I),
]
GA_RE = [
    re.compile(
        rf"\b(?:e?ga|gestational age|gestation){_SEP}(\d{{1,2}})\s*(?:weeks?|wks?|/40)?"
        r"(?:\s*(?:and\s*)?(\d)\s*days?)?",
        re.I,
    ),
    re.compile(
        r"(?<![\d/])(\d{1,2})\s*(?:weeks?|wks?)(?:\s*(?:and\s*)?(\d)\s*days?)?"
        r"\s*(?:pregnant|gestation|of pregnancy|into (?:the |her )?pregnancy)",
        re.I,
    ),
    re.compile(r"(?<![\d/])(\d{1,2})\s*/\s*40\b()", re.I),
]
GP_RE = re.compile(r"\bg\s*(\d{1,2})\s*p\s*(\d{1,2})(?:\s*\+\s*\d{1,2})?", re.I)
GRAVIDA_RE = re.compile(r"\bgravida\s*(\d{1,2})\b", re.I)
PARA_RE = re.compile(r"\bpara\s*(\d{1,2})\b", re.I)
PRIMIGRAVIDA_RE = re.compile(r"\bprimigravida\b|\bprimip\b", re.I)
_ORDINALS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
}
CONTACT_RE = [
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\s*(?:anc\s*)?(?:visit|contact)\b", re.I),
    re.compile(rf"\b({'|'.join(_ORDINALS)})\s*(?:anc\s*)?(?:visit|contact)\b", re.I),
]
BOOKING_RE = re.compile(r"\bbooking visit\b|\bbooked today\b", re.I)
_QUAL = r"(positive|negative|\+ve|-ve|pos|neg|non[- ]?reactive|reactive)"
_GRADE = r"(nil|negative|trace|\+{1,4}|[1-4]\s*\+)"
TEST_RE: list[tuple[LabTest, re.Pattern[str]]] = [
    (LabTest.pcv, re.compile(rf"\bpcv{_SEP}(\d{{1,2}}(?:[.,]\d+)?)\s*%?", re.I)),
    (LabTest.haemoglobin, re.compile(rf"\b(?:hb|ha?emoglobin){_SEP}(\d{{1,2}}(?:[.,]\d+)?)", re.I)),
    (LabTest.urine_protein, re.compile(rf"\b(?:urine\s*)?protein(?:uria)?{_SEP}{_GRADE}", re.I)),
    (LabTest.urine_glucose, re.compile(rf"\b(?:urine\s*)?(?:glucose|sugar){_SEP}{_GRADE}", re.I)),
    (LabTest.malaria_rdt, re.compile(rf"\b(?:m?rdt|malaria(?: rdt| test)?|mp){_SEP}{_QUAL}", re.I)),
    (LabTest.hiv, re.compile(rf"\b(?:hiv|rvs|retroviral screening)(?: test)?{_SEP}{_QUAL}", re.I)),
    (LabTest.syphilis, re.compile(rf"\b(?:vdrl|syphilis)(?: test)?{_SEP}{_QUAL}", re.I)),
    (LabTest.hepatitis_b, re.compile(rf"\b(?:hbsag|hepatitis b)(?: test)?{_SEP}{_QUAL}", re.I)),
]
REFER_RE = re.compile(
    r"\b(not |no )?refer(?:red|ring|ral)?\b(?:\s+(?:her|the patient|patient))?"
    r"(?:\s+to\s+(?:the\s+)?([a-z][\w .'-]{2,60}?)(?=[.,;\n]|$))?",
    re.I,
)
NEXT_VISIT_RE = re.compile(
    r"\b(?:tca|to come again|return|come back|next (?:visit|appointment|anc))\b[^.;\n]{0,40}",
    re.I,
)
DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _ev(text: str, m: re.Match[str]) -> Evidence:
    s, e = m.start(), m.end()
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    return Evidence(text=text[s:e], start=s, end=e)


def _first(patterns: list[re.Pattern[str]], text: str) -> Iterator[re.Match[str]]:
    for p in patterns:
        yield from p.finditer(text)


def extract_vitals(text: str) -> Vitals:
    v = Vitals()
    for m in BP_RE.finditer(text):
        sys_, dia = int(m.group(1)), int(m.group(2))
        if 60 <= sys_ <= 260 and 30 <= dia <= 160 and sys_ > dia:
            v.blood_pressure = BloodPressure(systolic=sys_, diastolic=dia, evidence=_ev(text, m))
            break
    for m in _first(TEMP_RE, text):
        value = _num(m.group(1))
        if 34 <= value <= 43:
            v.temperature = Temperature(value=value, evidence=_ev(text, m))
            break
    for m in _first(WEIGHT_RE, text):
        value = _num(m.group(1))
        if 25 <= value <= 200:
            v.weight = Weight(value=value, evidence=_ev(text, m))
            break
    for m in _first(PULSE_RE, text):
        value = int(m.group(1))
        if 30 <= value <= 250:
            v.pulse = Pulse(value=value, evidence=_ev(text, m))
            break
    return v


def _grade(raw: str) -> str:
    raw = raw.lower().replace(" ", "")
    if raw in ("nil", "negative"):
        return "negative"
    if raw == "trace":
        return "trace"
    if set(raw) == {"+"}:
        return f"{len(raw)}+"
    return raw  # already "2+"


def _qual(raw: str) -> str:
    raw = raw.lower().replace(" ", "").replace("-", "")
    if raw in ("positive", "+ve", "pos", "reactive"):
        return "positive"
    return "negative"


def extract_anc(text: str, folded: Folded, lex: Lexicon) -> Anc:
    anc = Anc()
    for m in _first(GA_RE, text):
        weeks = int(m.group(1))
        days = int(m.group(2)) if m.group(2) else None
        if 4 <= weeks <= 44:
            anc.gestational_age = GestationalAge(weeks=weeks, days=days, evidence=_ev(text, m))
            break
    if m := GP_RE.search(text):
        anc.gravida = Count(value=int(m.group(1)), evidence=_ev(text, m))
        anc.parity = Count(value=int(m.group(2)), evidence=_ev(text, m))
    else:
        if m := GRAVIDA_RE.search(text):
            anc.gravida = Count(value=int(m.group(1)), evidence=_ev(text, m))
        elif m := PRIMIGRAVIDA_RE.search(text):
            anc.gravida = Count(value=1, evidence=_ev(text, m))
        if m := PARA_RE.search(text):
            anc.parity = Count(value=int(m.group(1)), evidence=_ev(text, m))
    for m in _first(CONTACT_RE, text):
        raw = m.group(1).lower()
        value = _ORDINALS[raw] if raw in _ORDINALS else int(raw)
        anc.contact_number = Count(value=value, evidence=_ev(text, m))
        break
    else:
        if m := BOOKING_RE.search(text):
            anc.contact_number = Count(value=1, evidence=_ev(text, m))
    seen_tests: set[LabTest] = set()
    for test, pattern in TEST_RE:
        m = pattern.search(text)
        if not m or test in seen_tests:
            continue
        seen_tests.add(test)
        raw = m.group(1)
        if test in (LabTest.pcv, LabTest.haemoglobin):
            unit = "%" if test == LabTest.pcv else "g/dL"
            anc.tests.append(
                TestResult(test=test, value=_num(raw), unit=unit, evidence=_ev(text, m))
            )
        elif test in (LabTest.urine_protein, LabTest.urine_glucose):
            anc.tests.append(TestResult(test=test, result=_grade(raw), evidence=_ev(text, m)))  # pyright: ignore[reportArgumentType]
        else:
            anc.tests.append(TestResult(test=test, result=_qual(raw), evidence=_ev(text, m)))  # pyright: ignore[reportArgumentType]
    clauses = _clauses(folded.text, lex)
    for med, pattern in lex.medications.items():
        for m in pattern.finditer(folded.text):
            clause = clauses[_clause_at(clauses, m.start())]
            pre = folded.text[clause.start : m.start()]
            if lex.neg_pre.search(pre[pre.rfind(",") + 1 :]):
                continue
            anc.medications.append(
                MedicationGiven(medication=med, evidence=_evidence(folded, m.start(), m.end()))
            )
            break
    return anc


def extract_disposition(text: str) -> Disposition:
    d = Disposition()
    if m := REFER_RE.search(text):
        dest = m.group(2).strip() if m.group(2) else None
        d.referral = Referral(referred=m.group(1) is None, destination=dest, evidence=_ev(text, m))
    if m := NEXT_VISIT_RE.search(text):
        evidence = _ev(text, m)
        phrase = evidence.text
        date = None
        if dm := DATE_RE.search(phrase):
            try:
                date = dt.date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
            except ValueError:
                date = None
        d.next_visit = NextVisit(text=phrase[:100], date=date, evidence=evidence)
    return d


def extract(transcript: str) -> Encounter:
    """Draft an encounter record from ``transcript`` with keywords and regexes only."""
    text = normalise(transcript)
    lex = load_lexicon()
    ft = fold(text)
    return Encounter(
        findings=extract_findings(ft, lex),
        vitals=extract_vitals(text),
        anc=extract_anc(text, ft, lex),
        disposition=extract_disposition(text),
    )
