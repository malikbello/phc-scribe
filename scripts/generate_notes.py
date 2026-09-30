"""Generate the supplementary stratum G of ANC visit notes (ADR-0016).

    python scripts/generate_notes.py --n 300 --seed 20261002

Writes data/bench/g.<seed>.jsonl (generated text: no patient data, safe to commit)
and a report with verification counts next to it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.items import write_jsonl  # noqa: E402
from bench.notegen import generate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261002)
    parser.add_argument("--danger-share", type=float, default=0.4)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data" / "bench")
    parser.add_argument(
        "--stratum", choices=["G", "pilot"], default="G", help="pilot = dev items, never test"
    )
    args = parser.parse_args()
    items, report = generate(args.n, args.seed, args.danger_share, args.stratum)
    prefix = "g" if args.stratum == "G" else "pilot"
    out = args.out_dir / f"{prefix}.{args.seed}.jsonl"
    write_jsonl(out, items)
    out.with_suffix(".report.json").write_text(report.model_dump_json(indent=2) + "\n")
    lex_share = report.evidence_in_baseline_lexicon / max(1, report.evidence_quotes)
    print(
        f"{report.items} items -> {out}; "
        f"{report.with_positive_danger} with a present danger sign; "
        f"{len(report.rejected)} rejected; finding evidence in rung-1 lexicon: {lex_share:.0%}; "
        f"baseline extra concepts: {report.baseline_extra_concepts}"
    )
    return 1 if report.rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
