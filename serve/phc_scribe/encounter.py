"""Encounter record schema v0.1 (antenatal module).

These Pydantic models are the source of truth. ``schema/encounter.v0.1.json`` is
generated from them by ``scripts/export_schema.py`` and a test fails if the two drift.

Design notes (see docs/annotation-guidelines.md for the labelling rules):
- Only findings that are mentioned are listed. A concept that is not listed is
  implicitly ``not_mentioned``; emitting ``not_mentioned`` explicitly is allowed but
  carries no information and is ignored by the metrics.
- Every value carries ``evidence``: a verbatim quote from the transcript. Character
  offsets are filled in by the grounding step, not by the model.
- Units are UCUM codes, so vitals map straight onto FHIR Observations.
"""

from __future__ import annotations

import datetime as dt
import json
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from phc_scribe.vocab import load_vocabulary

SCHEMA_VERSION = "0.1.0"
SCHEMA_ID = "https://github.com/malikbello/phc-scribe/blob/main/schema/encounter.v0.1.json"

ConceptId = StrEnum("ConceptId", {c: c for c in load_vocabulary().ids})  # type: ignore[misc]


class Assertion(StrEnum):
    present = "present"
    absent = "absent"
    possible = "possible"
    historical = "historical"
    not_mentioned = "not_mentioned"


POSITIVE_ASSERTIONS = frozenset({Assertion.present, Assertion.possible})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(_Strict):
    text: str = Field(
        min_length=1,
        max_length=500,
        description="Verbatim quote from the transcript that supports the value.",
    )
    start: int | None = Field(
        default=None,
        ge=0,
        description="Start offset in the NFC transcript (code points). Set by grounding.",
    )
    end: int | None = Field(
        default=None,
        ge=0,
        description="End offset (exclusive) in the NFC transcript. Set by grounding.",
    )

    @model_validator(mode="after")
    def _offsets_consistent(self) -> Evidence:
        if (self.start is None) != (self.end is None):
            raise ValueError("start and end must be given together")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class Finding(_Strict):
    concept: ConceptId  # type: ignore[valid-type]
    assertion: Assertion
    evidence: Evidence | None = None

    @model_validator(mode="after")
    def _evidence_required(self) -> Finding:
        if self.assertion != Assertion.not_mentioned and self.evidence is None:
            raise ValueError("evidence is required unless assertion is not_mentioned")
        return self


class BloodPressure(_Strict):
    systolic: int = Field(description="mm[Hg]")
    diastolic: int = Field(description="mm[Hg]")
    unit: Literal["mm[Hg]"] = "mm[Hg]"
    evidence: Evidence


class Temperature(_Strict):
    value: float
    unit: Literal["Cel", "[degF]"] = "Cel"
    evidence: Evidence

    def celsius(self) -> float:
        return self.value if self.unit == "Cel" else (self.value - 32) * 5 / 9


class Weight(_Strict):
    value: float
    unit: Literal["kg"] = "kg"
    evidence: Evidence


class Pulse(_Strict):
    value: int
    unit: Literal["/min"] = "/min"
    evidence: Evidence


class Vitals(_Strict):
    blood_pressure: BloodPressure | None = None
    temperature: Temperature | None = None
    weight: Weight | None = None
    pulse: Pulse | None = None


class GestationalAge(_Strict):
    weeks: int
    days: int | None = Field(default=None, ge=0, le=6)
    evidence: Evidence


class Count(_Strict):
    value: int
    evidence: Evidence


class LabTest(StrEnum):
    malaria_rdt = "malaria_rdt"
    urine_protein = "urine_protein"
    urine_glucose = "urine_glucose"
    haemoglobin = "haemoglobin"
    pcv = "pcv"
    hiv = "hiv"
    syphilis = "syphilis"
    hepatitis_b = "hepatitis_b"


class TestResult(_Strict):
    __test__ = False  # not a pytest test class

    test: LabTest
    result: Literal["positive", "negative", "trace", "1+", "2+", "3+", "4+"] | None = Field(
        default=None, description="Qualitative result, if stated."
    )
    value: float | None = Field(default=None, description="Numeric result (Hb, PCV), if stated.")
    unit: Literal["g/dL", "%"] | None = None
    evidence: Evidence

    @model_validator(mode="after")
    def _has_result(self) -> TestResult:
        if self.result is None and self.value is None:
            raise ValueError("a test needs a qualitative result or a numeric value")
        if (self.value is None) != (self.unit is None):
            raise ValueError("value and unit must be given together")
        return self


class Medication(StrEnum):
    iron_folic_acid = "iron_folic_acid"
    ipt_sp = "ipt_sp"
    tetanus_diphtheria = "tetanus_diphtheria"
    deworming = "deworming"
    calcium = "calcium"
    other = "other"


class MedicationGiven(_Strict):
    medication: Medication
    name_text: str | None = Field(
        default=None, max_length=100, description="Name as said; required for `other`."
    )
    evidence: Evidence

    @model_validator(mode="after")
    def _other_named(self) -> MedicationGiven:
        if self.medication == Medication.other and not self.name_text:
            raise ValueError("name_text is required when medication is `other`")
        return self


class Anc(_Strict):
    gestational_age: GestationalAge | None = None
    gravida: Count | None = None
    parity: Count | None = None
    contact_number: Count | None = Field(default=None, description="ANC contact (visit) number.")
    tests: list[TestResult] = Field(default_factory=list)
    medications: list[MedicationGiven] = Field(default_factory=list)


class Referral(_Strict):
    referred: bool
    destination: str | None = Field(default=None, max_length=200)
    evidence: Evidence


class NextVisit(_Strict):
    text: str = Field(max_length=100, description="As said, e.g. 'in 4 weeks', 'TCA 2/52'.")
    date: dt.date | None = Field(default=None, description="Only if an explicit date was said.")
    evidence: Evidence


class Disposition(_Strict):
    referral: Referral | None = None
    next_visit: NextVisit | None = None


class Encounter(_Strict):
    """A drafted antenatal encounter record. A health worker must confirm it."""

    schema_version: Literal["0.1.0"] = SCHEMA_VERSION
    module: Literal["anc"] = "anc"
    findings: list[Finding] = Field(default_factory=list)
    vitals: Vitals = Field(default_factory=Vitals)
    anc: Anc = Field(default_factory=Anc)
    disposition: Disposition = Field(default_factory=Disposition)
    referral_summary: str | None = Field(
        default=None,
        max_length=600,
        description="Short English summary for the receiving facility. Human review only.",
    )

    @model_validator(mode="after")
    def _unique_findings(self) -> Encounter:
        seen: set[tuple[str, str]] = set()
        for f in self.findings:
            key = (str(f.concept), str(f.assertion))
            if key in seen:
                raise ValueError(f"duplicate finding {key}")
            seen.add(key)
        return self


def json_schema() -> dict[str, Any]:
    """The published JSON Schema for the record (the file in schema/)."""
    schema = Encounter.model_json_schema()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "PHC Scribe antenatal encounter record",
        "x-schema-version": SCHEMA_VERSION,
        "x-vocabulary-version": load_vocabulary().version,
        **{k: v for k, v in schema.items() if k != "title"},
    }


def dumps_json_schema() -> str:
    return json.dumps(json_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


# Upper bounds on the lists a model may generate (ADR-0024). The largest real gold
# records have 5 findings, 1 test and 2 medications, so these never cut a genuine
# record; they stop a degenerate loop that repeats an item until the token cap.
DECODING_MAX_ITEMS = {"findings": 10, "tests": 10, "medications": 10}


def decoding_schema() -> dict[str, Any]:
    """Schema for constrained decoding. The model quotes evidence; it never writes offsets.

    Every system is decoded against this same schema, so the list bounds apply to the
    base model and the fine-tuned model alike. The published schema stays unbounded.
    """
    schema = json_schema()
    evidence = schema["$defs"]["Evidence"]
    evidence["properties"] = {"text": evidence["properties"]["text"]}
    evidence["required"] = ["text"]
    schema["properties"]["findings"]["maxItems"] = DECODING_MAX_ITEMS["findings"]
    anc = schema["$defs"]["Anc"]["properties"]
    anc["tests"]["maxItems"] = DECODING_MAX_ITEMS["tests"]
    anc["medications"]["maxItems"] = DECODING_MAX_ITEMS["medications"]
    return schema
