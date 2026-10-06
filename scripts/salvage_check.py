"""Check the salvage step (ADR-0029) on non-test predictions only: dev and pilot.

    python scripts/salvage_check.py results/modal/*/pilot*.pred.jsonl

For each predictions file: how many outputs are schema-invalid, how many salvage turns
into a valid draft, which repairs it made, and that every already-valid output is left
untouched. Never run this on the frozen test sets to tune or choose anything (ADR-0022);
their post hoc effect is reported separately in docs/results-frozen-tests.md.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from phc_scribe.salvage import salvage


def check(path: Path) -> dict:
    if "frozen" in str(path):
        raise SystemExit(f"{path}: frozen test predictions are out of bounds here")
    n = invalid = salvaged = touched_valid = 0
    kinds: Counter[str] = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        p = json.loads(line)
        n += 1
        try:
            data = json.loads(p.get("raw_output") or "")
        except ValueError:
            data = None
        if p.get("record") is not None:
            touched_valid += salvage(data)[0] is not None
            continue
        invalid += 1
        record, repairs = salvage(data)
        if record is not None:
            salvaged += 1
            kinds.update(r.path.split("[")[0] for r in repairs)
    return {
        "items": n,
        "invalid": invalid,
        "salvaged": salvaged,
        "repairs": dict(kinds),
        "valid_outputs_changed": touched_valid,
    }


if __name__ == "__main__":
    report = {str(p): check(Path(p)) for p in sys.argv[1:]}
    print(json.dumps(report, indent=2))
