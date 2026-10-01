"""Fetch WazobiaSpeech health transcripts and build the ADR-0018 fallback S4 queue.

    python scripts/fetch_wazobia.py                        # dev_test, yo + pcm, 300 each
    python scripts/fetch_wazobia.py --per-language 300 --enriched-share 0.6
    python scripts/fetch_wazobia.py --check-speakers       # also check split disjointness

Only used if NigBench-MAMAI access has not arrived by 5 Oct (ADR-0018). Building the
queue labels nothing; it only prepares the switch.

Reads only the text columns of the parquet shards (column projection over HTTP range
requests), so the audio (about 230 GB for Yoruba alone) is never downloaded. The
datasets are ungated and CC-BY-4.0 (EqualyzAI / Data Science Nigeria).

Writes (all git-ignored, under data/private/):
- wazobia/<lang>_<split>_health.jsonl   every health clip's text + metadata
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

from bench.items import Language, write_jsonl  # noqa: E402
from bench.label_queue import (  # noqa: E402
    ENRICH_TERMS,
    SourceRow,
    enriched,
    keyword_hints,
    sample_enriched_queue,
)

# Our language code -> dataset repo. Revisions pinned when the cards were read
# (1 Oct 2026, 08:12 UTC). CC-BY-4.0 confirmed on both cards at these revisions.
DATASETS: dict[Language, tuple[str, str]] = {
    "yo": ("Africanvoice/yoruba_african_voices", "353ea9f10a1f67cda131ebb90f3205114be8ae58"),
    "pcm": ("Africanvoice/naija_african_voices", "2bb56186c314ea1f9c83951af3ae55b1703580a3"),
}
HEALTH_DOMAIN = "HE"
OUT_DIR = ROOT / "data" / "private" / "wazobia"
QUEUE_PATH = ROOT / "data" / "private" / "label_queue.s4w.jsonl"


def _shards(fs, repo: str, revision: str, split: str) -> list[str]:
    ref = f"datasets/{repo}@{revision}"
    names = [str(p) for p in fs.ls(f"{ref}/data", detail=False)]
    return sorted(p for p in names if Path(p).name.startswith(f"{split}-"))


def read_health_rows(lang: Language, split: str) -> list[SourceRow]:
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    repo, revision = DATASETS[lang]
    fs = HfFileSystem()
    paths = _shards(fs, repo, revision, split)
    if not paths:
        raise FileNotFoundError(f"no {split} shards for {repo}")
    rows: list[SourceRow] = []
    for path in paths:
        with fs.open(path, "rb", block_size=2**20) as f:
            table = pq.ParquetFile(f).read(
                columns=["transcript", "audio_id", "speaker_id", "domain"]
            )
        for rec in table.to_pylist():
            if rec.get("domain") != HEALTH_DOMAIN:
                continue
            rows.append(
                SourceRow(
                    source="wazobia",
                    source_id=str(rec["audio_id"]),
                    speaker_id=str(rec.get("speaker_id") or "unknown"),
                    language=lang,
                    split=split,
                    transcript=str(rec.get("transcript") or ""),
                )
            )
    return rows


def speaker_overlap(lang: Language, test_split: str) -> dict[str, int]:
    """Speakers shared between the test split and each other split, over all shards."""
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    repo, revision = DATASETS[lang]
    fs = HfFileSystem()
    speakers: dict[str, set[str]] = {}
    for split in ("train", "dev", "dev_test"):
        seen: set[str] = set()
        for path in _shards(fs, repo, revision, split):
            with fs.open(path, "rb", block_size=2**20) as f:
                col = pq.ParquetFile(f).read(columns=["speaker_id"]).column(0)
            seen.update(str(s) for s in col.to_pylist())
        speakers[split] = seen
    return {s: len(speakers[test_split] & speakers[s]) for s in speakers if s != test_split}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=["yo", "pcm"], choices=sorted(DATASETS))
    parser.add_argument("--split", default="dev_test")
    parser.add_argument("--per-language", type=int, default=300)
    parser.add_argument("--enriched-share", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=20261005)
    parser.add_argument("--no-hints", action="store_true", help="omit keyword hints")
    parser.add_argument(
        "--check-speakers", action="store_true", help="check split disjointness (slow)"
    )
    args = parser.parse_args()

    all_rows: list[SourceRow] = []
    pools: dict[str, dict[str, int]] = {}
    for lang in args.languages:
        try:
            rows = read_health_rows(lang, args.split)
        except Exception as e:
            fail(f"{lang}: {type(e).__name__}: {str(e).splitlines()[0][:200]}")
            return 1
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        write_jsonl(OUT_DIR / f"{lang}_{args.split}_health.jsonl", rows)
        n_enriched = sum(1 for r in rows if enriched(r.transcript))
        pools[lang] = {
            "health_clips": len(rows),
            "enriched": n_enriched,
            "speakers": len({r.speaker_id for r in rows}),
        }
        say(
            f"{lang}/{args.split}: {len(rows)} health clips, {n_enriched} match the"
            f" enrichment terms, {pools[lang]['speakers']} speakers"
        )
        all_rows.extend(rows)

    overlap = {}
    if args.check_speakers:
        for lang in args.languages:
            overlap[lang] = speaker_overlap(lang, args.split)
            say(f"{lang}: speakers shared with {args.split}: {overlap[lang]}")

    per_language = {lang: int(args.per_language) for lang in args.languages}
    hint_fn = None if args.no_hints else keyword_hints
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
        "split": args.split,
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
