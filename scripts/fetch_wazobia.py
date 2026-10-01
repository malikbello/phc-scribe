"""Fetch WazobiaSpeech health transcripts and build the ADR-0018 fallback S4 queue.

    python scripts/fetch_wazobia.py                        # dev + dev_test, yo + pcm, 300 each
    python scripts/fetch_wazobia.py --per-language 300 --enriched-share 0.6
    python scripts/fetch_wazobia.py --check-speakers       # also check split disjointness

Only used if NigBench-MAMAI access has not arrived by 5 Oct (ADR-0018). Building the
queue labels nothing; it only prepares the switch.

Reads only the text columns of the parquet shards (column projection over HTTP range
requests), so the audio (about 230 GB for Yoruba alone) is never downloaded. The
datasets are ungated and CC-BY-4.0 (EqualyzAI / Data Science Nigeria).

Writes (all git-ignored, under data/private/):
- wazobia/<lang>_<split>_health.jsonl   every health clip's text + metadata, per held-out split
- label_queue.s4w.jsonl                 the seeded, two-group (enriched/random) queue
- label_queue.s4w.meta.json             revision, seed, terms, group sizes

Prints counts only, never transcript text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT), str(ROOT / "scripts")]

from _safe_output import fail, say  # noqa: E402

from bench.items import write_jsonl  # noqa: E402
from bench.label_queue import (  # noqa: E402
    ENRICH_TERMS,
    SourceRow,
    enriched,
    keyword_hints,
    sample_enriched_queue,
)
from bench.wazobia import (  # noqa: E402
    DATASETS,
    HEALTH_DOMAIN,
    read_health_rows,
    speaker_overlap,
)

OUT_DIR = ROOT / "data" / "private" / "wazobia"
QUEUE_PATH = ROOT / "data" / "private" / "label_queue.s4w.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=["yo", "pcm"], choices=sorted(DATASETS))
    # Both held-out splits form the test pool (ADR-0018 amendment, 1 Oct): dev_test alone
    # has only 8 Yoruba and 11 Pidgin speakers. train stays for training.
    parser.add_argument("--splits", nargs="+", default=["dev", "dev_test"])
    parser.add_argument("--per-language", type=int, default=300)
    parser.add_argument("--enriched-share", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=20261005)
    # Off by default (guidelines §10.7): keyword hints would anchor labellers on the
    # rung-1 baseline the benchmark is meant to judge.
    parser.add_argument("--hints", action="store_true", help="add keyword-baseline hints")
    parser.add_argument(
        "--check-speakers", action="store_true", help="check split disjointness (slow)"
    )
    args = parser.parse_args()

    all_rows: list[SourceRow] = []
    pools: dict[str, dict[str, int]] = {}
    for lang in args.languages:
        try:
            rows = [r for split in args.splits for r in read_health_rows(lang, split)]
        except Exception as e:
            fail(f"{lang}: {type(e).__name__}: {str(e).splitlines()[0][:200]}")
            return 1
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for split in args.splits:
            write_jsonl(
                OUT_DIR / f"{lang}_{split}_health.jsonl", [r for r in rows if r.split == split]
            )
        n_enriched = sum(1 for r in rows if enriched(r.transcript))
        pools[lang] = {
            "health_clips": len(rows),
            "enriched": n_enriched,
            "speakers": len({r.speaker_id for r in rows}),
        }
        say(
            f"{lang}/{'+'.join(args.splits)}: {len(rows)} health clips, {n_enriched} match the"
            f" enrichment terms, {pools[lang]['speakers']} speakers"
        )
        all_rows.extend(rows)

    overlap = {}
    if args.check_speakers:
        for lang in args.languages:
            overlap[lang] = speaker_overlap(lang, args.splits)
            say(f"{lang}: speakers shared between train and the test pool: {overlap[lang]}")

    per_language = {lang: int(args.per_language) for lang in args.languages}
    hint_fn = keyword_hints if args.hints else None
    queue = sample_enriched_queue(
        all_rows, per_language, args.enriched_share, args.seed, hint_fn=hint_fn
    )
    write_jsonl(QUEUE_PATH, queue)
    groups = {
        f"{lang}/{g}": sum(1 for q in queue if q.language == lang and q.sampling == g)
        for lang in args.languages
        for g in ("enriched", "random")
    }
    say(f"queue: {len(queue)} items -> {QUEUE_PATH.relative_to(ROOT)} (seed {args.seed}; {groups})")
    meta = {
        "adr": "0018",
        "datasets": {
            lang: {"repo": DATASETS[lang][0], "revision": DATASETS[lang][1]}
            for lang in args.languages
        },
        "splits": args.splits,
        "domain": HEALTH_DOMAIN,
        "seed": args.seed,
        "per_language": per_language,
        "enriched_share": args.enriched_share,
        "enrich_terms": list(ENRICH_TERMS),
        "pools": pools,
        "groups": groups,
        "speaker_overlap": overlap or None,
        "items": len(queue),
    }
    QUEUE_PATH.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
