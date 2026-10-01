"""Build the S4-W calibration practice set (annotation guidelines §10.8).

    python scripts/build_s4w_calibration.py               # 10 per language, seed 20261001

Every labeller labels these clips before the counted queue, so disagreements about the
real-speech rules surface before they cost counted labels. Drawn from the same
WazobiaSpeech health pool as the counted queue (written by scripts/fetch_wazobia.py),
with the same enriched/random sampling, but **never** from the counted queue itself.
The clips are never counted and never used for prompts or few-shot examples.

Reads data/private/wazobia/*_health.jsonl and data/private/label_queue.s4w.jsonl; writes
data/private/label_queue.s4w-cal.jsonl (git-ignored). Upload it in the review app as a
practice set (Admin -> Add a labelling set -> "Everyone labels every item"). Prints counts
only, never transcript text.
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
from bench.label_queue import SourceRow, sample_enriched_queue  # noqa: E402

POOL_DIR = ROOT / "data" / "private" / "wazobia"
QUEUE_PATH = ROOT / "data" / "private" / "label_queue.s4w.jsonl"
OUT_PATH = ROOT / "data" / "private" / "label_queue.s4w-cal.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-language", type=int, default=10)
    parser.add_argument("--enriched-share", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=20261001)
    args = parser.parse_args()

    if not QUEUE_PATH.exists():
        fail(f"{QUEUE_PATH.relative_to(ROOT)} missing: run scripts/fetch_wazobia.py first")
        return 1
    queued = {
        json.loads(line)["source_id"]
        for line in QUEUE_PATH.read_text().splitlines()
        if line.strip()
    }
    rows = [
        SourceRow.model_validate_json(line)
        for path in sorted(POOL_DIR.glob("*_health.jsonl"))
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    pool = [r for r in rows if r.source_id not in queued]
    languages = sorted({r.language for r in pool})
    cal = sample_enriched_queue(
        pool,
        {lang: args.per_language for lang in languages},
        args.enriched_share,
        args.seed,
        prefix="s4wcal",
    )
    if {c.source_id for c in cal} & queued:
        fail("calibration overlaps the counted queue")
        return 1
    write_jsonl(OUT_PATH, cal)
    groups = {
        f"{lang}/{g}": sum(1 for c in cal if c.language == lang and c.sampling == g)
        for lang in languages
        for g in ("enriched", "random")
    }
    say(
        f"calibration: {len(cal)} items from {len(pool)} unqueued pool clips"
        f" -> {OUT_PATH.relative_to(ROOT)} (seed {args.seed}; {groups})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
