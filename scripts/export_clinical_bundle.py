"""Export the clinical bundle for the Takada app (ADR-0023 §1): rules, vocabulary, lexicon
forms and visit guide as one versioned, checksummed JSON, plus test vectors computed by
the Python reference implementation that the app's TypeScript port must reproduce.

    python scripts/export_clinical_bundle.py          # write exports/clinical-bundle.json
    python scripts/export_clinical_bundle.py --check  # exit 1 if the committed file is stale

The phone then applies exactly the rules and guide this repo tests and benchmarks. The
bundle holds project content only (no patient data). Nothing in it is cleared for
clinical use until the clinical adviser signs off (see `status`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from phc_scribe.rules import RULES_PATH, Facts, load_rules  # noqa: E402
from phc_scribe.text import fold_text  # noqa: E402
from phc_scribe.visit_guide import GUIDE_PATH, LEXICON_PATH, load_guide, load_raw  # noqa: E402
from phc_scribe.vocab import load_vocabulary  # noqa: E402

OUT = ROOT / "exports" / "clinical-bundle.json"

FOLD_VECTORS = [
    "Ẹ̀jẹ̀ ń jáde lára mi",
    "  Orí   ń fọ́ mi\tgidigidi ",
    "BP 160/110 — “severe” headache",
    "Ọmọ ń mì; ṣé ara rẹ̀ dá?",
    "Pikin dey KICK well-well",
    "àwọ̀n ẹ̀fọn",
]

GUIDE_VECTORS = [
    {"transcript": "", "facts": {}, "first_contact": None, "weeks": None},
    {
        "transcript": "Any bleeding? No. No headache.",
        "facts": {},
        "first_contact": False,
        "weeks": 30,
    },
    {"transcript": "ori n fo mi, pikin dey move", "facts": {}, "first_contact": True, "weeks": 24},
    {
        "transcript": "she has headache since morning",
        "facts": {"findings": {"headache": ["present"]}},
        "first_contact": False,
        "weeks": 32,
    },
    {
        "transcript": "hot body, BP 120/80, weight 70",
        "facts": {
            "findings": {"fever": ["present"]},
            "vitals": {"bp_systolic": 120, "bp_diastolic": 80, "weight_kg": 70},
        },
        "first_contact": False,
        "weeks": 20,
    },
    {
        "transcript": "baby no dey move like before, belle dey pain me",
        "facts": {
            "findings": {"reduced_fetal_movement": ["possible"], "abdominal_pain": ["present"]}
        },
        "first_contact": None,
        "weeks": 34,
    },
    {
        "transcript": (
            "Last period was in March. G3P2. She sleeps under a mosquito net, takes fefol."
        ),
        "facts": {},
        "first_contact": True,
        "weeks": 12,
    },
]


def build() -> dict:
    vocab = load_vocabulary()
    rules_raw = load_raw(RULES_PATH)
    rules = load_rules()
    guide = load_guide()
    lexicon = load_raw(LEXICON_PATH)
    rule_vectors = []
    for r in rules.rules:
        for t in r.tests:
            facts = {
                "findings": {k: sorted(v) for k, v in t.facts.findings.items()},
                "vitals": dict(t.facts.vitals),
                "tests": {k: list(v) for k, v in t.facts.tests.items()},
            }
            flags = rules.evaluate(t.facts)
            rule_vectors.append({"facts": facts, "flags": [f.rule_id for f in flags]})
    content = {
        "vocabulary": {
            "version": vocab.version,
            "concepts": [
                {
                    "id": c.id,
                    "label_en": c.label_en,
                    "danger_sign": c.danger_sign,
                    "definition": c.definition,
                }
                for c in vocab.concepts
            ],
        },
        "rules": rules_raw,
        "lexicon": {"version": lexicon.get("version"), "concepts": lexicon["concepts"]},
        "visit_guide": load_raw(GUIDE_PATH),
        "vectors": {
            "fold": [{"in": s, "out": fold_text(s)} for s in FOLD_VECTORS],
            "rules": rule_vectors,
            "guide": [
                {
                    **v,
                    "expect": guide.status(
                        v["transcript"], Facts.from_dict(v["facts"]), v["first_contact"], v["weeks"]
                    ),
                }
                for v in GUIDE_VECTORS
            ],
        },
    }
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {
        "format": "takada-clinical-bundle",
        "format_version": 1,
        "status": (
            "DRAFT: not for clinical use until every rule and guide item"
            " is signed off by the clinical adviser"
        ),
        "content_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        **content,
    }


def render() -> str:
    return json.dumps(build(), indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT.relative_to(ROOT)} is stale: run python scripts/export_clinical_bundle.py")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
