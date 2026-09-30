"""Regenerate the published API contract docs/openapi.v1.json from the FastAPI app.

python scripts/export_openapi.py          # write the file
python scripts/export_openapi.py --check  # exit 1 if the committed file is stale
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from phc_scribe.api.app import create_app  # noqa: E402
from phc_scribe.api.settings import Settings  # noqa: E402

OUT = ROOT / "docs" / "openapi.v1.json"


def render() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(env="dev", db_path=str(Path(tmp) / "x.sqlite3")))
        spec = app.openapi()
    return json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = render()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != current:
            print(f"{OUT} is stale: run python scripts/export_openapi.py")
            return 1
        print("openapi up to date")
        return 0
    OUT.write_text(current, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
