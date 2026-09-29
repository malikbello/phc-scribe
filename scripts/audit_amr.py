"""Gate 1 data audit of the African Medical Records dataset (docs/data-audit.md).

    pip install -e ".[data]"
    python scripts/audit_amr.py [--dataset ORG/NAME] [--revision SHA] [--max-rows N]

Writes:
- data/audit/amr_audit.json: aggregate counts only (committable)
- data/private/amr_samples.jsonl: a random sample of identifier-scrubbed notes for
  manual review (git-ignored; never committed, never printed)

Streams the dataset, so nothing large lands on disk. Image columns are counted, not
decoded. The revision is pinned in the report so the audit is reproducible.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT), str(ROOT / "scripts")]

from _safe_output import fail, say  # noqa: E402

from bench.data_audit import AuditCounts, card_topics  # noqa: E402
from phc_scribe.deid import scrub  # noqa: E402

DEFAULT_DATASET = "Nigeria-Health-data-OCR-pipeline/African-Medical-Records"
REPORT_PATH = ROOT / "data" / "audit" / "amr_audit.json"
SAMPLES_PATH = ROOT / "data" / "private" / "amr_samples.jsonl"
PROBE_ROWS = 200


def _file_summary(siblings: list[Any]) -> dict[str, Any]:
    by_ext: Counter[str] = Counter()
    size_by_ext: Counter[str] = Counter()
    for s in siblings:
        ext = Path(s.rfilename).suffix.lower() or "(none)"
        by_ext[ext] += 1
        size_by_ext[ext] += s.size or 0
    return {
        "files": len(siblings),
        "total_mb": round(sum(size_by_ext.values()) / 1e6, 1),
        "by_extension": {
            e: {"files": n, "mb": round(size_by_ext[e] / 1e6, 1)} for e, n in by_ext.most_common()
        },
    }


def _columns(features: Any) -> tuple[list[str], list[str], dict[str, str]]:
    from datasets import Image, Value

    text, images, kinds = [], [], {}
    for name, feat in (features or {}).items():
        kinds[name] = type(feat).__name__ + (f"({feat.dtype})" if isinstance(feat, Value) else "")
        if isinstance(feat, Value) and feat.dtype in ("string", "large_string"):
            text.append(name)
        elif isinstance(feat, Image):
            images.append(name)
    return text, images, kinds


def _pick_text_column(
    rows: list[dict[str, Any]], candidates: list[str]
) -> tuple[str | None, dict[str, float]]:
    avg = {c: sum(len(str(r.get(c) or "")) for r in rows) / max(1, len(rows)) for c in candidates}
    best = max(avg, key=lambda c: avg[c]) if avg else None
    return best, {c: round(v, 1) for c, v in avg.items()}


def audit_split(
    ds: Any, split: str, args: argparse.Namespace, samples: list[dict[str, str]]
) -> dict[str, Any]:
    from datasets import Image

    text_cols, image_cols, kinds = _columns(ds.features)
    for col in image_cols:
        ds = ds.cast_column(col, Image(decode=False))
    it = iter(ds)
    probe = [row for _, row in zip(range(PROBE_ROWS), it, strict=False)]
    text_col = args.text_column if args.text_column else None
    chosen, avg_len = _pick_text_column(probe, text_cols)
    text_col = text_col or chosen
    result: dict[str, Any] = {
        "columns": kinds,
        "text_columns_avg_chars": avg_len,
        "image_columns": image_cols,
        "text_column_used": text_col,
    }
    if text_col is None:
        n = len(probe) + sum(1 for _ in it)
        result["rows"] = n
        result["note"] = "no text column: notes are images only, OCR or transcription needed"
        return result

    counts = AuditCounts()
    rng = random.Random(args.seed)  # noqa: S311 (sampling, not security)
    seen = 0

    def rows():
        yield from probe
        yield from it

    for row in rows():
        if args.max_rows and seen >= args.max_rows:
            break
        text = str(row.get(text_col) or "")
        counts.add(text)
        seen += 1
        # reservoir sample for manual review (scrubbed, private, never printed)
        entry = {"split": split, "row": str(seen - 1), "text_scrubbed": scrub(text)}
        if len(samples) < args.samples:
            samples.append(entry)
        elif (j := rng.randrange(seen)) < args.samples:
            samples[j] = entry
    result["rows_audited"] = seen
    result["summary"] = counts.summary()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--revision", help="commit sha to pin (default: current main)")
    parser.add_argument("--text-column", help="override the auto-picked text column")
    parser.add_argument("--max-rows", type=int, default=0, help="0 = all rows")
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    try:
        from datasets import load_dataset
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as e:
        fail(f"missing dependency ({e.name}); run: pip install -e '.[data]'")
        return 1

    api = HfApi()
    info = api.dataset_info(args.dataset, revision=args.revision, files_metadata=True)
    revision = info.sha
    say(f"dataset {args.dataset} @ {revision}")
    card_meta = info.card_data.to_dict() if info.card_data else {}
    try:
        card_path = hf_hub_download(
            args.dataset, "README.md", repo_type="dataset", revision=revision
        )
        card = Path(card_path).read_text(encoding="utf-8")
    except Exception as e:
        fail(f"no dataset card: {type(e).__name__}")
        card = ""

    report: dict[str, Any] = {
        "dataset": args.dataset,
        "revision": revision,
        "audited_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "card": {
            "license": card_meta.get("license"),
            "gated": info.gated,
            "task_categories": card_meta.get("task_categories"),
            "languages": card_meta.get("language"),
            "card_chars": len(card),
            "topic_mentions": card_topics(card),
        },
        "files": _file_summary(info.siblings or []),
        "splits": {},
    }

    samples: list[dict[str, str]] = []
    dsd = load_dataset(args.dataset, revision=revision, streaming=True)
    for split, ds in dsd.items():
        say(f"auditing split {split} ...")
        report["splits"][str(split)] = audit_split(ds, str(split), args, samples)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    SAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLES_PATH.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    say(
        f"wrote {REPORT_PATH.relative_to(ROOT)} (aggregates) and {len(samples)} scrubbed samples to"
    )
    say(f"  {SAMPLES_PATH.relative_to(ROOT)} (private, git-ignored)")
    for split, r in report["splits"].items():
        s = r.get("summary", {})
        say(
            f"  {split}: rows={r.get('rows_audited', r.get('rows'))}"
            f" text_column={r.get('text_column_used')}"
            f" primary_visit_type={s.get('visit_type_primary')}"
            f" language={s.get('language_guess')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
