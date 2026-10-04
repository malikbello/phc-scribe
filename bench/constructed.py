"""Stratum S5: constructed Yoruba and Pidgin patient statements with gold by construction
(pre-freeze audit C1, 4 Oct 2026).

    python -m bench.constructed --out data/bench/s5.20261004.jsonl

Why: the real-speech set S4-W has about 2.5% danger-sign prevalence, too few to test P1
(danger-sign recall) in Yoruba or Pidgin. No open real antenatal-consultation speech exists
in those languages (MAMAI is still gated). Mature health benchmarks solve this with
constructed cases whose answers are fixed by design (HealthBench's synthetic conversations
with physician rubrics; ACI-Bench's and AfriSpeech-Dialog's role-played consultations).

How: each item is composed from `data/bench/constructed/s5.lexicon.v0.yaml` by a seeded
sampler. A finding's evidence is the exact clause placed in the transcript, so the gold is
exact. Item mix per language: about 52% with a danger sign (present or possible), 30% with
other findings or denied/past danger signs, 18% general talk with nothing to record. Danger
concepts are drawn round-robin so rare signs are covered. Severity pairs never co-occur.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import yaml

from bench.items import BenchItem, write_jsonl
from phc_scribe.encounter import Encounter
from phc_scribe.vocab import load_vocabulary

LEXICON = (
    Path(__file__).resolve().parents[1] / "data" / "bench" / "constructed" / "s5.lexicon.v0.yaml"
)
SEED = 20261011
SEVERITY_PAIRS = [
    ("severe_headache", "headache"),
    ("severe_abdominal_pain", "abdominal_pain"),
    ("severe_vomiting", "nausea_vomiting"),
]
MIX = {"danger": 0.52, "other": 0.30, "none": 0.18}


def _conflicts(concept: str) -> set[str]:
    out = {concept}
    for a, b in SEVERITY_PAIRS:
        if concept in (a, b):
            out |= {a, b}
    return out


def _add(picks: list[tuple[str, str]], concept: str, assertion: str) -> None:
    """Add a finding unless its concept, or its severity partner, is already in the item."""
    used = set().union(*(_conflicts(c) for c, _ in picks)) if picks else set()
    if not (_conflicts(concept) & used):
        picks.append((concept, assertion))


def build(lexicon: dict, per_language: int, seed: int = SEED) -> list[BenchItem]:
    rng = random.Random(seed)  # noqa: S311 (test construction, not security)
    danger_ids = load_vocabulary().danger_sign_ids
    items: list[BenchItem] = []
    for lang, lex in sorted(lexicon["languages"].items()):
        concepts = lex["concepts"]
        danger_pos = sorted(
            c for c in concepts if c in danger_ids and {"present", "possible"} & set(concepts[c])
        )
        danger_neg = sorted(
            (c, a) for c in concepts if c in danger_ids for a in ("absent", "historical")
            if a in concepts[c]
        )  # fmt: skip
        other = sorted(
            (c, a) for c in concepts if c not in danger_ids for a in concepts[c]
        )  # fmt: skip
        counts = {k: round(per_language * v) for k, v in MIX.items()}
        counts["other"] = per_language - counts["danger"] - counts["none"]
        kinds = [k for k, n in counts.items() for _ in range(n)]
        rng.shuffle(kinds)
        robin = danger_pos * (per_language // max(1, len(danger_pos)) + 1)
        rng.shuffle(robin)
        for n, kind in enumerate(kinds):
            picks: list[tuple[str, str]] = []
            if kind == "danger":
                c = robin.pop()
                forms = [a for a in ("present", "possible") if a in concepts[c]]
                _add(
                    picks,
                    c,
                    "present" if "possible" not in forms or rng.random() < 0.7 else "possible",
                )
                for _ in range(rng.choice([0, 1, 1, 2])):
                    pool = other + danger_neg
                    _add(picks, *pool[rng.randrange(len(pool))])
            elif kind == "other":
                pool = other + danger_neg
                for _ in range(rng.choice([1, 1, 2])):
                    _add(picks, *pool[rng.randrange(len(pool))])
            clauses = [(c, a, rng.choice(concepts[c][a])) for c, a in picks]
            sentences = [f"{text}." for _, _, text in clauses]
            if kind == "none" or rng.random() < 0.25:
                sentences.insert(rng.randrange(len(sentences) + 1), rng.choice(lex["general"]))
            rng.shuffle(sentences)
            if rng.random() < 0.6:
                sentences.insert(0, rng.choice(lex["openers"]))
            transcript = " ".join(sentences)
            gold = Encounter.model_validate(
                {
                    "findings": [
                        {"concept": c, "assertion": a, "evidence": {"text": text}}
                        for c, a, text in clauses
                    ]
                }
            )
            for f in gold.findings:
                if not (f.evidence and f.evidence.text in transcript):
                    raise ValueError(f"evidence not in transcript: {f.concept}")
            items.append(
                BenchItem(
                    item_id=f"s5-{lang}-{n:03d}",
                    group_id=f"s5:{lang}-{n:03d}",
                    stratum="S5",
                    language=lang,
                    origin="constructed",
                    transcript=transcript,
                    gold=gold,
                )
            )
    return items


def summary(items: list[BenchItem]) -> dict:
    danger_ids = load_vocabulary().danger_sign_ids
    out: dict = {}
    for lang in sorted({i.language for i in items}):
        sub = [i for i in items if i.language == lang]
        pos = [
            f
            for i in sub
            for f in i.gold.findings
            if str(f.concept) in danger_ids and str(f.assertion) in ("present", "possible")
        ]
        out[lang] = {
            "items": len(sub),
            "items_with_danger_sign": sum(
                any(
                    str(f.concept) in danger_ids and str(f.assertion) in ("present", "possible")
                    for f in i.gold.findings
                )
                for i in sub
            ),
            "danger_positive_findings": len(pos),
            "nothing_to_record": sum(not i.gold.findings for i in sub),
            "danger_concepts": dict(sorted(Counter(str(f.concept) for f in pos).items())),
            "assertions": dict(
                sorted(Counter(str(f.assertion) for i in sub for f in i.gold.findings).items())
            ),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-language", type=int, default=150)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    lexicon = yaml.safe_load(LEXICON.read_text(encoding="utf-8"))
    items = build(lexicon, args.per_language, args.seed)
    write_jsonl(args.out, items)
    report = {"lexicon": lexicon["version"], "seed": args.seed, **summary(items)}
    args.out.with_suffix(".report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
