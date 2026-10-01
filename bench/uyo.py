"""Stratum U: check the danger-sign rules on real Uyo antenatal records (ADR-0019).

The records are structured (one symptom label, one diagnosis, vitals per visit), so this
tests the rules engine, not the language model. The mapping below is fixed before any
result is looked at; the clinical adviser confirms it before the first real run.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from phc_scribe.encounter import (
    Assertion,
    BloodPressure,
    Encounter,
    Evidence,
    Finding,
    LabTest,
    Temperature,
    TestResult,
    Vitals,
)
from phc_scribe.rules import RuleSet, check

# Uyo symptom label (lower case, spaces collapsed) -> our findings, all "present".
# Labels not listed here record no finding. "High blood pressure" maps to nothing: the
# measured BP is in the record and the BP rules use that.
SYMPTOM_FINDINGS: dict[str, tuple[str, ...]] = {
    "bleeding per vaginam": ("vaginal_bleeding",),
    "bleeding": ("vaginal_bleeding",),
    "swollen legs": ("leg_oedema",),
    "swollen legs and high bp": ("leg_oedema",),
    "severe headache": ("severe_headache",),
    "headache, pains and cough": ("headache", "cough"),
    "difficult breathing": ("breathing_difficulty",),
    "abnormal breathing": ("breathing_difficulty",),
    "liquor drainage": ("leaking_amniotic_fluid",),
    "lower abdominal and waist pain": ("abdominal_pain", "low_back_pain"),
    "abdominal pain": ("abdominal_pain",),
    "waist pain": ("low_back_pain",),
    "dizziness, itching body": ("dizziness",),
    "painful urination": ("painful_urination",),
    "pain in urination": ("painful_urination",),
    "itching per vaginam and watery discharge": ("abnormal_vaginal_discharge",),
    "itching pv and watery discharge": ("abnormal_vaginal_discharge",),
    "heart burn": ("heartburn",),
    "stooling and vomiting": ("nausea_vomiting",),
    "fever, sneezing, and cough": ("fever", "cough"),
    "itching body, cough and fever": ("fever", "cough"),
    "boils on the body and fever": ("fever",),
    "body pain and fever": ("fever",),
    "cough and fever": ("fever", "cough"),
    "cough and catarrh": ("cough",),
    "sore throat and cough": ("cough",),
    "cough and sore throat": ("cough",),
    "severe cough": ("cough",),
    "cough": ("cough",),
    "weakness of the body": ("fatigue",),
}
# Symptom labels that are a urine test result rather than a finding.
URINE_PROTEIN_LABELS = {"protein in urine"}

# Clinician diagnoses treated as danger diagnoses (a referral flag is expected).
DANGER_DIAGNOSES = {
    "eclampsia",
    "pre eclampsia",
    "hypertension",
    "high blood pressure",
    "antepartum haemorrhage",
    "placenta previa",
    "proteinuria",
}
HYPERTENSIVE_DIAGNOSES = {"eclampsia", "pre eclampsia", "hypertension", "high blood pressure"}
NORMAL_DIAGNOSIS = "normal scan result"


def _norm(label: object) -> str:
    return re.sub(r"\s+", " ", str(label or "")).strip().lower()


@dataclass(frozen=True)
class UyoRecord:
    patient: str
    symptom: str
    diagnosis: str
    bp: str
    temperature: str


def to_encounter(rec: UyoRecord) -> Encounter:
    """The record as our schema sees it. Evidence quotes the source field."""
    vitals = Vitals()
    m = re.fullmatch(r"\s*(\d{2,3})\s*/\s*(\d{2,3})\s*", rec.bp)
    if m:
        vitals.blood_pressure = BloodPressure(
            systolic=int(m.group(1)),
            diastolic=int(m.group(2)),
            evidence=Evidence(text=rec.bp.strip()),
        )
    try:
        temp = float(rec.temperature)
    except ValueError:
        temp = None
    if temp is not None:
        vitals.temperature = Temperature(
            value=temp, evidence=Evidence(text=str(rec.temperature).strip())
        )
    label = _norm(rec.symptom)
    findings = [
        Finding(concept=c, assertion=Assertion.present, evidence=Evidence(text=rec.symptom.strip()))
        for c in SYMPTOM_FINDINGS.get(label, ())
    ]
    record = Encounter(findings=findings, vitals=vitals)
    if label in URINE_PROTEIN_LABELS:
        record.anc.tests.append(
            TestResult(
                test=LabTest.urine_protein,
                result="positive",
                evidence=Evidence(text=rec.symptom.strip()),
            )
        )
    return record


@dataclass(frozen=True)
class Proportion:
    k: int
    n: int

    @property
    def point(self) -> float | None:
        return self.k / self.n if self.n else None

    def ci(self, alpha: float = 0.05) -> tuple[float, float] | None:
        return clopper_pearson(self.k, self.n, alpha) if self.n else None


def _binom_cdf(k: int, n: int, p: float) -> float:
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def _solve(f, lo: float = 0.0, hi: float = 1.0) -> float:
    """Root of a decreasing function on [lo, hi] by bisection."""
    for _ in range(80):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial confidence interval."""
    # lower: P(X >= k | p) = alpha/2, which rises with p; upper: P(X <= k | p) = alpha/2.
    lower = 0.0 if k == 0 else _solve(lambda p: alpha / 2 - (1 - _binom_cdf(k - 1, n, p)))
    upper = 1.0 if k == n else _solve(lambda p: _binom_cdf(k, n, p) - alpha / 2)
    return lower, upper


def evaluate(
    records: Iterable[UyoRecord], rules: RuleSet | None = None
) -> dict[str, Proportion | Mapping[str, int]]:
    """Flag the records and compare with the clinician diagnosis (ADR-0019 §3)."""
    danger = Proportion(0, 0)
    bp = Proportion(0, 0)
    normal = Proportion(0, 0)
    per_rule: dict[str, int] = {}
    for rec in records:
        flags = check(to_encounter(rec), rules)
        fired = bool(flags)
        bp_fired = any(f.rule_id.startswith(("VS-", "CB-")) for f in flags)
        for f in flags:
            per_rule[f.rule_id] = per_rule.get(f.rule_id, 0) + 1
        dx = _norm(rec.diagnosis)
        if dx in DANGER_DIAGNOSES:
            danger = Proportion(danger.k + fired, danger.n + 1)
        if dx in HYPERTENSIVE_DIAGNOSES:
            bp = Proportion(bp.k + bp_fired, bp.n + 1)
        if dx == NORMAL_DIAGNOSIS:
            normal = Proportion(normal.k + fired, normal.n + 1)
    return {
        "danger_diagnosis_flagged": danger,
        "hypertensive_diagnosis_bp_flag": bp,
        "normal_scan_flagged": normal,
        "flags_per_rule": dict(sorted(per_rule.items())),
    }
