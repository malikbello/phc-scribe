"""Salvage a schema-invalid model output instead of rejecting the whole record (ADR-0029).

The model sometimes writes an otherwise good record with one part the schema forbids. Three
repairs, fixed in advance, each removing only a part that carries no clinical content or
repeats one already kept:

1. a test with neither a qualitative result nor a numeric value ("urine protein" with no
   result): there is nothing to record;
2. a medication coded ``other`` with no name: the record cannot say what was given;
3. a repeated finding (same concept and assertion): the first is kept.

Nothing is invented, no value is changed, and invalid JSON is never patched. Every repair is
reported, so the health worker reviews the draft knowing what was removed. Salvage runs only
after strict validation fails, so a valid output is never touched.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from phc_scribe.encounter import Encounter


@dataclass(frozen=True)
class Repair:
    path: str
    detail: str


def salvage(data: Any) -> tuple[Encounter | None, list[Repair]]:
    """Apply the three repairs to parsed model output; ``(None, [])`` if it still fails."""
    if not isinstance(data, dict):
        return None, []
    data = copy.deepcopy(data)
    repairs: list[Repair] = []
    anc = data.get("anc")
    if isinstance(anc, dict):
        tests = anc.get("tests")
        if isinstance(tests, list):
            kept = []
            for i, t in enumerate(tests):
                if isinstance(t, dict) and t.get("result") is None and t.get("value") is None:
                    repairs.append(Repair(f"anc.tests[{i}]", f"{t.get('test')}: no result"))
                else:
                    kept.append(t)
            anc["tests"] = kept
        meds = anc.get("medications")
        if isinstance(meds, list):
            kept = []
            for i, m in enumerate(meds):
                if (
                    isinstance(m, dict)
                    and m.get("medication") == "other"
                    and not m.get("name_text")
                ):
                    repairs.append(Repair(f"anc.medications[{i}]", "other: no name"))
                else:
                    kept.append(m)
            anc["medications"] = kept
    findings = data.get("findings")
    if isinstance(findings, list):
        seen: set[tuple[Any, Any]] = set()
        kept = []
        for i, f in enumerate(findings):
            key = (f.get("concept"), f.get("assertion")) if isinstance(f, dict) else (i, None)
            if key in seen:
                repairs.append(Repair(f"findings[{i}]", f"duplicate {key[0]} ({key[1]})"))
            else:
                seen.add(key)
                kept.append(f)
        data["findings"] = kept
    if not repairs:
        return None, []
    try:
        return Encounter.model_validate(data), repairs
    except ValueError:
        return None, []
