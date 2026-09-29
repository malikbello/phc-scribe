"""Deterministic danger-sign rules engine (ADR-0003).

Rules are data (rules/danger_signs.v0.yaml). Conditions are a small declarative
language checked at load time: a typo in a concept or vital name fails loudly instead
of silently never firing. No ``eval``. Missing data never matches, and a finding that
is ``possible`` counts the same as ``present`` (safety first).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from phc_scribe.encounter import Encounter
from phc_scribe.vocab import REPO_ROOT, load_vocabulary

RULES_PATH = REPO_ROOT / "rules" / "danger_signs.v0.yaml"

DEFAULT_ASSERTIONS = frozenset({"present", "possible"})
VITALS = frozenset({"bp_systolic", "bp_diastolic", "temperature_c", "pulse", "weight_kg"})
TESTS = frozenset(
    {
        "haemoglobin",
        "pcv",
        "urine_protein",
        "urine_glucose",
        "malaria_rdt",
        "hiv",
        "syphilis",
        "hepatitis_b",
    }
)
SEVERITY_ORDER = {"urgent_referral": 0, "refer": 1}
_COMPARATORS = {
    "gte": lambda a, b: a >= b,
    "gt": lambda a, b: a > b,
    "lte": lambda a, b: a <= b,
    "lt": lambda a, b: a < b,
}


@dataclass(frozen=True)
class Facts:
    """What the rules can see: asserted findings, numeric vitals, lab results."""

    findings: Mapping[str, frozenset[str]]
    vitals: Mapping[str, float]
    tests: Mapping[str, tuple[float | str, ...]]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Facts:
        tests: dict[str, tuple[float | str, ...]] = {}
        for name, value in (data.get("tests") or {}).items():
            tests[name] = tuple(value) if isinstance(value, list) else (value,)
        return cls(
            findings={k: frozenset(v) for k, v in (data.get("findings") or {}).items()},
            vitals={k: float(v) for k, v in (data.get("vitals") or {}).items()},
            tests=tests,
        )

    @classmethod
    def from_encounter(cls, record: Encounter) -> Facts:
        findings: dict[str, set[str]] = {}
        for f in record.findings:
            findings.setdefault(str(f.concept), set()).add(str(f.assertion))
        vitals: dict[str, float] = {}
        v = record.vitals
        if v.blood_pressure:
            vitals["bp_systolic"] = v.blood_pressure.systolic
            vitals["bp_diastolic"] = v.blood_pressure.diastolic
        if v.temperature:
            vitals["temperature_c"] = v.temperature.celsius()
        if v.pulse:
            vitals["pulse"] = v.pulse.value
        if v.weight:
            vitals["weight_kg"] = v.weight.value
        tests: dict[str, list[float | str]] = {}
        for t in record.anc.tests:
            values = tests.setdefault(str(t.test), [])
            if t.value is not None:
                values.append(t.value)
            if t.result is not None:
                values.append(t.result)
        return cls(
            findings={k: frozenset(s) for k, s in findings.items()},
            vitals=vitals,
            tests={k: tuple(vs) for k, vs in tests.items()},
        )


def _check_numeric(spec: Mapping[str, Any], where: str) -> None:
    ops = set(spec) - {"name"}
    if not ops or not ops <= set(_COMPARATORS) | {"in"}:
        raise ValueError(f"{where}: needs one of gte/gt/lte/lt/in, got {sorted(ops)}")


def validate_condition(cond: Any, where: str) -> None:
    """Raise ValueError if ``cond`` is not a well-formed condition."""
    if not isinstance(cond, Mapping) or len(cond) != 1:
        raise ValueError(f"{where}: a condition is a mapping with exactly one key")
    ((kind, spec),) = cond.items()
    concepts = set(load_vocabulary().ids)
    if kind in ("any", "all"):
        if not isinstance(spec, list) or not spec:
            raise ValueError(f"{where}: {kind} needs a non-empty list")
        for i, sub in enumerate(spec):
            validate_condition(sub, f"{where}.{kind}[{i}]")
    elif kind == "finding":
        concept = spec if isinstance(spec, str) else spec.get("concept")
        if concept not in concepts:
            raise ValueError(f"{where}: unknown concept {concept!r}")
    elif kind == "vital":
        if spec.get("name") not in VITALS:
            raise ValueError(f"{where}: unknown vital {spec.get('name')!r}")
        _check_numeric(spec, where)
    elif kind == "test":
        if spec.get("name") not in TESTS:
            raise ValueError(f"{where}: unknown test {spec.get('name')!r}")
        _check_numeric(spec, where)
    else:
        raise ValueError(f"{where}: unknown condition {kind!r}")


def _value_matches(spec: Mapping[str, Any], value: float | str) -> bool:
    for op, target in spec.items():
        if op == "name":
            continue
        if op == "in":
            if value not in target:
                return False
        elif isinstance(value, str) or not _COMPARATORS[op](value, target):
            return False
    return True


def matches(cond: Mapping[str, Any], facts: Facts) -> bool:
    ((kind, spec),) = cond.items()
    if kind == "any":
        return any(matches(c, facts) for c in spec)
    if kind == "all":
        return all(matches(c, facts) for c in spec)
    if kind == "finding":
        if isinstance(spec, str):
            concept, wanted = spec, DEFAULT_ASSERTIONS
        else:
            concept, wanted = spec["concept"], frozenset(spec.get("assertion", DEFAULT_ASSERTIONS))
        return bool(facts.findings.get(concept, frozenset()) & wanted)
    if kind == "vital":
        value = facts.vitals.get(spec["name"])
        return value is not None and _value_matches(spec, value)
    if kind == "test":
        return any(_value_matches(spec, v) for v in facts.tests.get(spec["name"], ()))
    raise ValueError(f"unknown condition {kind!r}")


@dataclass(frozen=True)
class RuleTest:
    name: str
    facts: Facts
    fires: bool


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: str
    when: Mapping[str, Any]
    message_en: str
    source_ref: str
    source_section: str
    source_verified: bool
    supersedes: tuple[str, ...]
    tests: tuple[RuleTest, ...]

    def fires(self, facts: Facts) -> bool:
        return matches(self.when, facts)


@dataclass(frozen=True)
class Flag:
    rule_id: str
    name: str
    severity: str
    message_en: str
    source_ref: str
    source_section: str


@dataclass(frozen=True)
class RuleSet:
    version: str
    rules: tuple[Rule, ...]

    def evaluate(self, facts: Facts) -> list[Flag]:
        """Fired rules, minus superseded ones, most severe first."""
        fired = [r for r in self.rules if r.fires(facts)]
        superseded = {s for r in fired for s in r.supersedes}
        flags = [
            Flag(r.id, r.name, r.severity, r.message_en, r.source_ref, r.source_section)
            for r in fired
            if r.id not in superseded
        ]
        return sorted(flags, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule_id))


def parse_rules(data: Mapping[str, Any]) -> RuleSet:
    sources = data.get("sources") or {}
    severities = set(data.get("severities") or {})
    if severities != set(SEVERITY_ORDER):
        raise ValueError(f"severities must be exactly {sorted(SEVERITY_ORDER)}")
    rules: list[Rule] = []
    for raw in data["rules"]:
        rid = raw["id"]
        if raw["severity"] not in SEVERITY_ORDER:
            raise ValueError(f"{rid}: unknown severity {raw['severity']!r}")
        if raw["source"]["ref"] not in sources:
            raise ValueError(f"{rid}: unknown source {raw['source']['ref']!r}")
        validate_condition(raw["when"], rid)
        tests = tuple(
            RuleTest(t["name"], Facts.from_dict(t.get("facts") or {}), bool(t["fires"]))
            for t in raw.get("tests") or ()
        )
        if not tests:
            raise ValueError(f"{rid}: every rule needs at least one golden test")
        rules.append(
            Rule(
                id=rid,
                name=raw["name"],
                severity=raw["severity"],
                when=raw["when"],
                message_en=raw["message_en"],
                source_ref=raw["source"]["ref"],
                source_section=raw["source"].get("section", ""),
                source_verified=bool(raw["source"].get("verified", False)),
                supersedes=tuple(raw.get("supersedes") or ()),
                tests=tests,
            )
        )
    ids = [r.id for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate rule ids")
    unknown = {s for r in rules for s in r.supersedes} - set(ids)
    if unknown:
        raise ValueError(f"supersedes unknown rules: {sorted(unknown)}")
    return RuleSet(version=str(data["version"]), rules=tuple(rules))


@cache
def load_rules(path: Path = RULES_PATH) -> RuleSet:
    with path.open(encoding="utf-8") as f:
        return parse_rules(yaml.safe_load(f))


def check(record: Encounter, rules: RuleSet | None = None) -> list[Flag]:
    """Danger-sign flags for a record (the /v1/check operation)."""
    return (rules or load_rules()).evaluate(Facts.from_encounter(record))
