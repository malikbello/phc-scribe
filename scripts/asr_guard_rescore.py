"""Apply the ASR decoding guard (audit H4) to saved transcripts, for re-scoring as shipped.

    python scripts/asr_guard_rescore.py data/private/kaggle/asr-ft-forced.jsonl \
        data/private/kaggle/asr-ft-forced.guarded.jsonl

Reads a bench.asr_run output (one line per clip: audio_id, language, reference, text) and
writes the same lines with `text` passed through phc_scribe.asr_guard.guard, plus
`guard_cut: true` where a loop was cut. Then re-score with scripts/asr_compare.py, base and
fine-tuned both guarded. Prints counts only, never transcript text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from phc_scribe.asr_guard import guard  # noqa: E402


def main(src: Path, dst: Path) -> dict[str, int]:
    rows, cut = [], 0
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row["text"], row["guard_cut"] = guard(row.get("text") or "")
        cut += row["guard_cut"]
        rows.append(json.dumps(row, ensure_ascii=False))
    dst.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"clips": len(rows), "loops_cut": cut}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print(json.dumps(main(Path(sys.argv[1]), Path(sys.argv[2]))))
