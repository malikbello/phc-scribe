"""Test items for the ASR-input condition (eval plan §6a; audit H2).

    python scripts/build_asr_items.py --items data/bench/s4w.jsonl \
        --asr data/private/kaggle/asr-ft-forced.jsonl --out data/bench/s4w.asr-ft.jsonl

Each S4-W item keeps its gold labels (made from the human transcript) and its ids; the
transcript is replaced by the ASR output for the same clip. The system then reads the
ASR text, so its errors count against it, as in service. Predictions are grounded against
the ASR text; gold evidence is not re-grounded (it quotes the human transcript). An item
with no ASR output is reported, never dropped silently. Prints counts only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.items import BenchItem, read_jsonl, write_jsonl  # noqa: E402


def asr_items(items: list[BenchItem], asr: dict[str, str], prefix: str) -> tuple[list, list]:
    out, missing = [], []
    for item in items:
        audio_id = item.item_id.split("-", 2)[2]  # s4w-<lang>-<audio_id>
        text = asr.get(audio_id)
        if text is None:
            missing.append(item.item_id)
            continue
        out.append(
            item.model_copy(update={"transcript": text, "item_id": f"{prefix}{item.item_id}"})
        )
    return out, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--asr", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prefix", default="asr-")
    args = parser.parse_args()
    rows = [json.loads(x) for x in args.asr.read_text(encoding="utf-8").splitlines() if x.strip()]
    asr = {r["audio_id"]: r["text"] for r in rows}
    items, missing = asr_items(list(read_jsonl(args.items, BenchItem)), asr, args.prefix)
    write_jsonl(args.out, items)
    print(f"{len(items)} ASR-input items -> {args.out}; {len(missing)} without ASR output")
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
