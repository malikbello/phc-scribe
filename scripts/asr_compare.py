"""ADR-0026 evaluation: paired WER comparison of two ASR runs on the same test-pool clips.

    python scripts/asr_compare.py --base data/private/kaggle/asr-base-forced.jsonl \
        --candidate data/private/kaggle/asr-ft-forced.jsonl \
        --out results/asr/ft-vs-base.json

Each input is a bench.asr_run output (one line per clip: audio_id, language, reference,
text). Per language: pooled WER and CER for both systems, and the 95% paired-bootstrap CI of
the WER difference (candidate - base), resampling speakers (the queue's group_id) so clips
from one speaker move together. ADR-0026 ship rule: the fine-tuned model replaces the base
only if the CI lies entirely below zero. Writes aggregates only; prints no transcript text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.stats import Ratio, paired_bootstrap_diff  # noqa: E402
from bench.two_view import fold  # noqa: E402
from bench.wer import edit_errors  # noqa: E402

QUEUE = ROOT / "data" / "private" / "label_queue.s4w.jsonl"


def char_errors(reference: str, hypothesis: str) -> tuple[int, int]:
    ref, hyp = list(fold(reference).replace(" ", "")), list(fold(hypothesis).replace(" ", ""))
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (r != h))
    return row[-1], len(ref)


def load(path: Path) -> dict[str, dict]:
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return {r["audio_id"]: r for r in rows}


def compare(base: dict[str, dict], cand: dict[str, dict], speaker: dict[str, str]) -> dict:
    out: dict = {}
    for lang in sorted({r["language"] for r in base.values()}):
        ids = sorted(a for a, r in base.items() if r["language"] == lang and a in cand)
        if not ids:
            continue
        res: dict = {"clips": len(ids), "speakers": len({speaker.get(a, a) for a in ids})}
        ratios = {}
        for name, runs in (("base", base), ("candidate", cand)):
            w = [edit_errors(runs[a]["reference"], runs[a]["text"]) for a in ids]
            c = [char_errors(runs[a]["reference"], runs[a]["text"]) for a in ids]
            ratios[name] = Ratio.of([e for e, _ in w], [n for _, n in w])
            res[f"{name}_wer"] = round(ratios[name].value(), 4)
            res[f"{name}_cer"] = round(sum(e for e, _ in c) / max(1, sum(n for _, n in c)), 4)
        diff = paired_bootstrap_diff(
            ratios["base"], ratios["candidate"], groups=[speaker.get(a, a) for a in ids]
        )
        res["wer_diff"] = {"point": round(diff.point, 4), "low": round(diff.low, 4),
                           "high": round(diff.high, 4)}  # fmt: skip
        res["relative_wer_reduction"] = round(1 - res["candidate_wer"] / res["base_wer"], 4)
        res["ship"] = diff.high < 0
        out[lang] = res
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    speaker = {}
    if QUEUE.exists():
        for x in QUEUE.read_text(encoding="utf-8").splitlines():
            if x.strip():
                q = json.loads(x)
                speaker[q["source_id"]] = q["group_id"]
    result = {
        "base": args.base.name,
        "candidate": args.candidate.name,
        "metric": "pooled WER/CER, folded text (bench/wer.py); 95% paired bootstrap over speakers",
        "languages": compare(load(args.base), load(args.candidate), speaker),
    }
    print(json.dumps(result["languages"], indent=1))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
