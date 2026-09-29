"""Regenerate schema/encounter.v0.1.json from the Pydantic models.

python scripts/export_schema.py          # write the file
python scripts/export_schema.py --check  # exit 1 if the committed file is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "serve"))

from phc_scribe.encounter import dumps_json_schema
from phc_scribe.vocab import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema" / "encounter.v0.1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = dumps_json_schema()
    if args.check:
        if not SCHEMA_PATH.exists() or SCHEMA_PATH.read_text(encoding="utf-8") != current:
            print(f"{SCHEMA_PATH} is stale: run python scripts/export_schema.py")
            return 1
        print("schema up to date")
        return 0
    SCHEMA_PATH.write_text(current, encoding="utf-8")
    print(f"wrote {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
