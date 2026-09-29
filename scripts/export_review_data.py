"""Export the review content (vocabulary, rules, phrase bank, open questions) as JSON
for the review web app (review-app/src/data/review.json).

    python scripts/export_review_data.py          # write
    python scripts/export_review_data.py --check  # exit 1 if the committed file is stale

Everything here is non-sensitive project content; the app bundles it. Benchmark items
are never bundled: they are uploaded to the app's server-side store by the admin.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT), str(ROOT / "scripts")]

from build_review_pack import GUIDELINES, PHRASES, RULES, condition  # noqa: E402

from phc_scribe.grounding import MIN_QUOTE_CHARS  # noqa: E402
from phc_scribe.vocab import load_vocabulary  # noqa: E402

OUT = ROOT / "review-app" / "src" / "data" / "review.json"


def _plain(html_text: str) -> str:
    return re.sub(r"<[^>]+>", "", html_text).replace("&amp;", "&").replace("&#x27;", "'")


def build() -> str:
    vocab = load_vocabulary()
    labels = {c.id: c.label_en for c in vocab.concepts}
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    phrases = yaml.safe_load(PHRASES.read_text(encoding="utf-8"))
    guide = GUIDELINES.read_text(encoding="utf-8")
    m = re.search(r"## 9\. Open questions.*?\n(.*?)(?:\n## |\Z)", guide, re.S)
    questions = re.findall(r"^\d+\.\s+(.*)$", m.group(1), re.M) if m else []
    data = {
        "vocabulary_version": vocab.version,
        # evidence quotes shorter than this (after folding) fail grounding
        "min_quote_chars": MIN_QUOTE_CHARS,
        "concepts": [
            {
                "id": c.id,
                "label": c.label_en,
                "danger": c.danger_sign,
                "definition": c.definition,
            }
            for c in vocab.concepts
        ],
        "rules": [
            {
                "id": r["id"],
                "name": r["name"],
                "when": _plain(condition(r["when"], labels)),
                "message": r.get("message_en", ""),
                "severity": r.get("severity", ""),
            }
            for r in rules["rules"]
        ],
        "phrases": [
            {"concept": cid, "label": labels[cid], "forms": spec["forms"]}
            for cid, spec in phrases["concepts"].items()
        ],
        "questions": [_plain(q) for q in questions],
    }
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = build()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(
                "review.json is stale; run: python scripts/export_review_data.py", file=sys.stderr
            )
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
