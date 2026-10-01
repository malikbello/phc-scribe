"""Teacher labels for real training speech (ADR-0021).

    python -m bench.teacher fetch --out teacher.items.jsonl          # on Kaggle (needs HF)
    python -m bench.teacher filter --items teacher.items.jsonl \
        --pred teacher.preds.jsonl --out teacher.kept.jsonl

`fetch` samples WazobiaSpeech `train` health clips (training split only; the test pool is
`dev` + `dev_test`, with 0 shared speakers, ADR-0018), enriched toward ANC terms, as
stratum-T items with an empty placeholder gold. Llama-3.1-8B few-shot then labels them
(bench.runners.llm). `filter` applies the ADR-0021 rule, fixed before use:
- the output is schema-valid;
- every evidence quote is found verbatim in the transcript (our grounding check drops
  nothing, and no quote matches only after folding tone marks);
- items with no finding are kept, but are at most half of the kept set.
Kept items carry the teacher's grounded record as gold. Prints counts only.
"""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import BaseModel

from bench.items import BenchItem, Language, Prediction, read_jsonl, write_jsonl
from bench.label_queue import SourceRow, sample_enriched_queue
from phc_scribe.encounter import Encounter
from phc_scribe.grounding import ground

SEED = 20261006  # differs from every test-set seed


class TeacherReport(BaseModel):
    items: int = 0
    no_prediction: int = 0
    invalid: int = 0
    ungrounded: int = 0
    not_verbatim: int = 0
    kept_with_findings: int = 0
    kept_empty: int = 0
    empty_over_cap: int = 0


def to_items(
    rows: Iterable[SourceRow], per_language: int, enriched_share: float, seed: int = SEED
) -> list[BenchItem]:
    rows = list(rows)
    langs = sorted({r.language for r in rows})
    queue = sample_enriched_queue(
        rows, dict.fromkeys(langs, per_language), enriched_share, seed, prefix="t"
    )
    return [
        BenchItem(
            item_id=q.item_id,
            group_id=q.group_id,
            stratum="T",
            language=q.language,
            origin="real",
            transcript=q.transcript,
            gold=Encounter(),
        )
        for q in queue
    ]


def filter_teacher(
    items: Sequence[BenchItem],
    preds: Iterable[Prediction],
    seed: int = SEED,
    empty_cap: float = 0.5,
) -> tuple[list[BenchItem], TeacherReport]:
    by_id = {p.item_id: p for p in preds}
    report = TeacherReport(items=len(items))
    full: list[BenchItem] = []
    empty: list[BenchItem] = []
    for item in items:
        pred = by_id.get(item.item_id)
        if pred is None:
            report.no_prediction += 1
            continue
        if pred.record is None:
            report.invalid += 1
            continue
        g = ground(pred.record, item.transcript)
        if g.dropped:
            report.ungrounded += 1
            continue
        if g.folded_matches:
            report.not_verbatim += 1
            continue
        kept = item.model_copy(update={"gold": g.record})
        (full if g.record.findings else empty).append(kept)
    # Empty items may be at most `empty_cap` of the kept set.
    allowed = int(len(full) * empty_cap / (1 - empty_cap)) if empty_cap < 1 else len(empty)
    rng = random.Random(seed)  # noqa: S311 (sampling, not security)
    empty_sorted = sorted(empty, key=lambda i: i.item_id)
    rng.shuffle(empty_sorted)
    keep_empty = empty_sorted[:allowed]
    report.kept_with_findings = len(full)
    report.kept_empty = len(keep_empty)
    report.empty_over_cap = len(empty) - len(keep_empty)
    kept = sorted(full + keep_empty, key=lambda i: i.item_id)
    return kept, report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--languages", nargs="+", default=["yo", "pcm"])
    f.add_argument("--per-language", type=int, default=300)
    f.add_argument("--enriched-share", type=float, default=0.8)
    f.add_argument("--max-shards", type=int, default=40)
    f.add_argument("--seed", type=int, default=SEED)
    k = sub.add_parser("filter")
    k.add_argument("--items", type=Path, required=True)
    k.add_argument("--pred", type=Path, required=True)
    k.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.cmd == "fetch":
        from bench.wazobia import read_health_rows

        langs: list[Language] = list(args.languages)
        rows = [r for lang in langs for r in read_health_rows(lang, "train", args.max_shards)]
        items = to_items(rows, args.per_language, args.enriched_share, args.seed)
        write_jsonl(args.out, items)
        print(f"teacher items: {len(items)} from {len(rows)} train health clips -> {args.out}")
        return 0
    items = list(read_jsonl(args.items, BenchItem))
    kept, report = filter_teacher(items, read_jsonl(args.pred, Prediction))
    write_jsonl(args.out, kept)
    print(f"=== TEACHER {json.dumps(report.model_dump())}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
