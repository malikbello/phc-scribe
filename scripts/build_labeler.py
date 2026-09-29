"""Build tools/labeler/labeler.html from its template plus the concept vocabulary.

python scripts/build_labeler.py          # write
python scripts/build_labeler.py --check  # exit 1 if the committed file is stale (CI)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from phc_scribe.vocab import load_vocabulary  # noqa: E402

TEMPLATE = ROOT / "tools" / "labeler" / "labeler.template.html"
OUTPUT = ROOT / "tools" / "labeler" / "labeler.html"
PLACEHOLDER = "/*VOCAB*/null"


def render() -> str:
    vocab = load_vocabulary()
    payload = {
        "version": vocab.version,
        "concepts": [
            {"id": c.id, "label_en": c.label_en, "danger_sign": c.danger_sign}
            for c in vocab.concepts
        ],
    }
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise ValueError(f"{TEMPLATE} must contain {PLACEHOLDER} exactly once")
    # "</" cannot appear inside a <script> element's JSON.
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(PLACEHOLDER, blob)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    html = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != html:
            print("labeler.html is stale; run: python scripts/build_labeler.py", file=sys.stderr)
            return 1
        return 0
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
