"""Fetch NigBench-MAMAI transcripts and build the S4 label queue (ADR-0016).

    python scripts/fetch_mamai.py                      # test split, yo + pcm, 300 each
    python scripts/fetch_mamai.py --per-language 300 --languages Yoruba Pidgin Hausa

Reads only the text columns of the parquet files (column projection over HTTP range
requests), so the ~59 GB of audio is never downloaded. Needs approved access to the
gated dataset on the HF account behind HF_TOKEN.

Writes (all git-ignored, under data/private/):
- mamai/<Language>_<split>.jsonl   every utterance's text + metadata
- label_queue.s4.jsonl             the seeded, language-stratified queue for the labeler

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
    MAMAI_LANGUAGES,
    SourceRow,
    keyword_hints,
    sample_queue,
)

DATASET = "intronhealth/NigBench-MAMAI-Speech-QA"
REVISION = "63b8620d7b7cf9a50544fa13ecd11f80f6adcb13"  # audited 29 Sept 2026
OUT_DIR = ROOT / "data" / "private" / "mamai"
QUEUE_PATH = ROOT / "data" / "private" / "label_queue.s4.jsonl"


def read_text_columns(language: str, split: str, revision: str) -> list[SourceRow]:
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    fs = HfFileSystem()
    base = f"datasets/{DATASET}@{revision}/{language}"
    names = [str(p) for p in fs.ls(base, detail=False)]
    paths = sorted(p for p in names if Path(p).name.startswith(f"{split}-"))
    if not paths:
        raise FileNotFoundError(f"no {split} files for {language}")
    rows: list[SourceRow] = []
    for path in paths:
        with fs.open(path, "rb") as f:
            pf = pq.ParquetFile(f)
            cols = [c for c in pf.schema_arrow.names if c != "audio"]
            for rec in pf.read(columns=cols).to_pylist():
                rows.append(
                    SourceRow(
                        source="mamai",
                        source_id=str(rec["sample_id"]),
                        speaker_id=str(rec.get("speaker_id") or "unknown"),
                        language=MAMAI_LANGUAGES[language],
                        split=split,
                        transcript=str(rec.get("transcript") or ""),
                        audio_duration=rec.get("audio_duration"),
                    )
                )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", default=["Yoruba", "Pidgin"])
    parser.add_argument("--split", default="test")
    parser.add_argument("--per-language", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--revision", default=REVISION)
    parser.add_argument("--no-hints", action="store_true", help="omit keyword hints")
    args = parser.parse_args()

    unknown = [lang for lang in args.languages if lang not in MAMAI_LANGUAGES]
    if unknown:
        fail(f"unsupported languages {unknown}; choose from {sorted(MAMAI_LANGUAGES)}")
        return 2

    all_rows: list[SourceRow] = []
    for language in args.languages:
        try:
            rows = read_text_columns(language, args.split, args.revision)
        except Exception as e:
            msg = str(e)
            if "awaiting a review" in msg:
                fail(f"{language}: access still pending approval by the dataset authors")
            else:
                fail(f"{language}: {type(e).__name__}: {msg.splitlines()[0][:200]}")
            return 1
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        n = write_jsonl(OUT_DIR / f"{language}_{args.split}.jsonl", rows)
        speakers = len({r.speaker_id for r in rows})
        empty = sum(1 for r in rows if not r.transcript.strip())
        say(f"{language}/{args.split}: {n} utterances, {speakers} speakers, {empty} empty")
        all_rows.extend(rows)

    per_language = {MAMAI_LANGUAGES[lang]: args.per_language for lang in args.languages}
    hint_fn = None if args.no_hints else keyword_hints
    queue = sample_queue(all_rows, per_language, args.seed, hint_fn=hint_fn)
    write_jsonl(QUEUE_PATH, queue)
    with_hints = sum(1 for q in queue if q.hints)
    say(
        f"queue: {len(queue)} items -> {QUEUE_PATH.relative_to(ROOT)}"
        f" (seed {args.seed}; {with_hints} with keyword hints)"
    )
    meta = {
        "dataset": DATASET,
        "revision": args.revision,
        "split": args.split,
        "seed": args.seed,
        "per_language": per_language,
        "items": len(queue),
    }
    (QUEUE_PATH.with_suffix(".meta.json")).write_text(json.dumps(meta, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
