"""Stratum R: red-team items with gold by construction (eval plan §6a; audit H5).

    python -m bench.redteam --out data/bench/r.20261004.jsonl

Reads `data/bench/constructed/r.v0.yaml` (one item per failure mode: negation lists and
scope, hedging, third parties, past vs current, embedded instructions, hypotheticals,
questions, severity, examination findings, numbers, code-switching, a reported pregnant
patient), checks that every evidence quote is in its transcript, and writes bench items.
Reported separately; no pass/fail criterion.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import yaml

from bench.items import BenchItem, write_jsonl
from phc_scribe.encounter import Encounter

SOURCE = Path(__file__).resolve().parents[1] / "data" / "bench" / "constructed" / "r.v0.yaml"


def build(spec: dict) -> list[BenchItem]:
    items = []
    for row in spec["items"]:
        text = row["transcript"]
        data: dict = {
            "findings": [
                {"concept": c, "assertion": a, "evidence": {"text": q}}
                for c, a, q in row["findings"]
            ]
        }
        if row.get("bp"):
            sys_, dia, q = row["bp"]
            data["vitals"] = {
                "blood_pressure": {"systolic": sys_, "diastolic": dia, "evidence": {"text": q}}
            }
        quotes = [q for _, _, q in row["findings"]] + ([row["bp"][2]] if row.get("bp") else [])
        missing = [q for q in quotes if q not in text]
        if missing:
            raise ValueError(f"{row['id']}: evidence not in transcript: {missing}")
        items.append(
            BenchItem(
                item_id=f"r-{row['id']}",
                group_id=f"r:{row['id']}",
                stratum="R",
                language=row["language"],
                origin="constructed",
                transcript=text,
                gold=Encounter.model_validate(data),
            )
        )
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    items = build(yaml.safe_load(SOURCE.read_text(encoding="utf-8")))
    write_jsonl(args.out, items)
    langs = dict(Counter(i.language for i in items))
    print(f"{len(items)} red-team items -> {args.out}; by language {langs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
