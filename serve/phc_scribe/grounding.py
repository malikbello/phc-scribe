"""Grounding and value checks: pipeline steps 4 and 5 (docs/architecture.md, section 2).

Every drafted value must quote its evidence from the transcript. Here we:
1. find each quote in the transcript (exact first, then diacritic/case/whitespace
   folded) and record its offsets;
2. check numbers against physiological ranges and against the digits in the quote;
3. drop anything that fails and mark the record NEEDS_REVIEW.

Nothing is repaired by guessing: a field is either supported by the transcript or it
goes to a human.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from phc_scribe.encounter import (
    Anc,
    Assertion,
    Disposition,
    Encounter,
    Evidence,
    LabTest,
    Vitals,
)
from phc_scribe.text import fold, fold_text, normalise

MIN_QUOTE_CHARS = 2
MatchLevel = Literal["exact", "folded"]
DropReason = Literal["ungrounded", "out_of_range", "value_not_in_evidence", "inconsistent"]

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class Located:
    start: int
    end: int
    level: MatchLevel


@dataclass(frozen=True)
class DroppedField:
    path: str
    reason: DropReason
    detail: str = ""


@dataclass
class GroundingResult:
    record: Encounter
    fields_total: int = 0
    dropped: list[DroppedField] = field(default_factory=list)
    folded_matches: int = 0

    @property
    def needs_review(self) -> bool:
        return bool(self.dropped)

    @property
    def ungrounded(self) -> int:
        return sum(1 for d in self.dropped if d.reason == "ungrounded")


def _nearest(starts: list[int], hint: int | None) -> int:
    if hint is None:
        return starts[0]
    return min(starts, key=lambda s: abs(s - hint))


def _find_all(haystack: str, needle: str) -> list[int]:
    out: list[int] = []
    i = haystack.find(needle)
    while i != -1:
        out.append(i)
        i = haystack.find(needle, i + 1)
    return out


def locate(transcript: str, quote: str, hint: int | None = None) -> Located | None:
    """Find ``quote`` in ``transcript`` (both NFC). Returns source offsets or None."""
    quote = normalise(quote).strip()
    folded_quote = fold_text(quote).strip()
    if len(folded_quote) < MIN_QUOTE_CHARS:
        return None
    starts = _find_all(transcript, quote)
    if starts:
        s = _nearest(starts, hint)
        return Located(s, s + len(quote), "exact")
    ft = fold(transcript)
    starts = _find_all(ft.text, folded_quote)
    if not starts:
        return None
    s = _nearest([ft.index[i] for i in starts], hint)
    fs = next(i for i in starts if ft.index[i] == s)
    start, end = ft.to_source_span(fs, fs + len(folded_quote))
    return Located(start, end, "folded")


def _numbers(text: str) -> list[float]:
    return [float(n.replace(",", ".")) for n in _NUMBER.findall(text)]


def _value_in_evidence(values: Sequence[float], evidence: Evidence) -> bool:
    """Numbers said as words (common in Yoruba) cannot be checked, so they pass."""
    found = _numbers(evidence.text)
    if not found:
        return True
    return all(any(abs(v - n) < 1e-6 for n in found) for v in values)


# Physiological ranges: wide on purpose. They catch garbage, not clinical abnormality.
RANGES: dict[str, tuple[float, float]] = {
    "bp_systolic": (50, 300),
    "bp_diastolic": (20, 200),
    "temperature_c": (30, 45),
    "weight_kg": (20, 250),
    "pulse": (30, 250),
    "ga_weeks": (1, 45),
    "gravida": (1, 20),
    "parity": (0, 20),
    "contact_number": (1, 20),
    "haemoglobin_g_dl": (2, 25),
    "pcv_percent": (5, 70),
}


def _in_range(name: str, value: float) -> bool:
    lo, hi = RANGES[name]
    return lo <= value <= hi


class _Grounder:
    def __init__(self, transcript: str, result: GroundingResult) -> None:
        self.transcript = transcript
        self.result = result

    def evidence(self, path: str, evidence: Evidence) -> Evidence | None:
        self.result.fields_total += 1
        found = locate(self.transcript, evidence.text, hint=evidence.start)
        if found is None:
            self.drop(path, "ungrounded", "quote not found in transcript")
            return None
        if found.level == "folded":
            self.result.folded_matches += 1
        return Evidence(
            text=self.transcript[found.start : found.end], start=found.start, end=found.end
        )

    def drop(self, path: str, reason: DropReason, detail: str = "") -> None:
        self.result.dropped.append(DroppedField(path, reason, detail))

    def check(
        self,
        path: str,
        checks: Sequence[tuple[str, float]],
        evidence: Evidence,
        said: Sequence[float] | None = None,
    ) -> bool:
        """Range-check ``checks``; ``said`` (default: the checked values) must be in the quote."""
        for name, value in checks:
            if not _in_range(name, value):
                self.drop(path, "out_of_range", f"{name}={value}")
                return False
        if not _value_in_evidence(said if said is not None else [v for _, v in checks], evidence):
            self.drop(path, "value_not_in_evidence", evidence.text)
            return False
        return True


def _ground_vitals(g: _Grounder, vitals: Vitals) -> Vitals:
    out = Vitals()
    if (bp := vitals.blood_pressure) and (ev := g.evidence("vitals.blood_pressure", bp.evidence)):
        path = "vitals.blood_pressure"
        checks = [("bp_systolic", bp.systolic), ("bp_diastolic", bp.diastolic)]
        if bp.systolic <= bp.diastolic:
            g.drop(path, "inconsistent", "systolic must exceed diastolic")
        elif g.check(path, checks, ev):
            out.blood_pressure = bp.model_copy(update={"evidence": ev})
    if (t := vitals.temperature) and (ev := g.evidence("vitals.temperature", t.evidence)):
        path = "vitals.temperature"
        if g.check(path, [("temperature_c", t.celsius())], ev, said=[t.value]):
            out.temperature = t.model_copy(update={"evidence": ev})
    if (
        (w := vitals.weight)
        and (ev := g.evidence("vitals.weight", w.evidence))
        and g.check("vitals.weight", [("weight_kg", w.value)], ev)
    ):
        out.weight = w.model_copy(update={"evidence": ev})
    if (
        (p := vitals.pulse)
        and (ev := g.evidence("vitals.pulse", p.evidence))
        and g.check("vitals.pulse", [("pulse", p.value)], ev)
    ):
        out.pulse = p.model_copy(update={"evidence": ev})
    return out


_TEST_RANGE: dict[LabTest, tuple[str, str]] = {
    LabTest.haemoglobin: ("haemoglobin_g_dl", "g/dL"),
    LabTest.pcv: ("pcv_percent", "%"),
}


def _ground_anc(g: _Grounder, anc: Anc) -> Anc:
    out = Anc()
    if (
        (ga := anc.gestational_age)
        and (ev := g.evidence("anc.gestational_age", ga.evidence))
        and g.check("anc.gestational_age", [("ga_weeks", ga.weeks)], ev)
    ):
        out.gestational_age = ga.model_copy(update={"evidence": ev})
    for name in ("gravida", "parity", "contact_number"):
        count = getattr(anc, name)
        if (
            count
            and (ev := g.evidence(f"anc.{name}", count.evidence))
            and g.check(f"anc.{name}", [(name, count.value)], ev)
        ):
            setattr(out, name, count.model_copy(update={"evidence": ev}))
    if out.gravida and out.parity and out.parity.value > out.gravida.value:
        g.drop("anc.parity", "inconsistent", "parity exceeds gravida")
        out.parity = None
    for i, test in enumerate(anc.tests):
        path = f"anc.tests[{i}]"
        if not (ev := g.evidence(path, test.evidence)):
            continue
        if test.value is not None:
            expected = _TEST_RANGE.get(test.test)
            if expected is None or test.unit != expected[1]:
                g.drop(path, "inconsistent", f"no numeric value expected for {test.test}")
                continue
            if not g.check(path, [(expected[0], test.value)], ev):
                continue
        out.tests.append(test.model_copy(update={"evidence": ev}))
    for i, med in enumerate(anc.medications):
        if ev := g.evidence(f"anc.medications[{i}]", med.evidence):
            out.medications.append(med.model_copy(update={"evidence": ev}))
    return out


def _ground_disposition(g: _Grounder, disposition: Disposition) -> Disposition:
    out = Disposition()
    if (r := disposition.referral) and (ev := g.evidence("disposition.referral", r.evidence)):
        out.referral = r.model_copy(update={"evidence": ev})
    nv = disposition.next_visit
    if nv and (ev := g.evidence("disposition.next_visit", nv.evidence)):
        out.next_visit = nv.model_copy(update={"evidence": ev})
    return out


def ground(record: Encounter, transcript: str) -> GroundingResult:
    """Ground ``record`` against ``transcript``; unsupported fields are dropped."""
    transcript = normalise(transcript)
    result = GroundingResult(record=record)
    g = _Grounder(transcript, result)

    findings = []
    for i, f in enumerate(record.findings):
        if f.assertion == Assertion.not_mentioned:
            continue  # carries no information; nothing to ground
        if f.evidence is None:  # unreachable: the Finding validator requires evidence
            continue
        if ev := g.evidence(f"findings[{i}]", f.evidence):
            findings.append(f.model_copy(update={"evidence": ev}))

    result.record = record.model_copy(
        update={
            "findings": findings,
            "vitals": _ground_vitals(g, record.vitals),
            "anc": _ground_anc(g, record.anc),
            "disposition": _ground_disposition(g, record.disposition),
        }
    )
    return result
