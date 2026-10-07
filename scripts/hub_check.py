"""Check a running /v1 API end to end, as the clinic hub serves it: speed and correctness.

    PHC_API_KEY=... python scripts/hub_check.py --url http://127.0.0.1:8000 --tag laptop-i7

Sends non-test items (default: the 30 pilot items) to `/v1/extract` one at a time, as the
hub's queue does, and reports:
- seconds per draft (p50, p95, max; the first, cold request reported apart);
- danger-sign recall and false alarms against the items' gold labels, with the benchmark's
  own scorer (bench.metrics.score_item), plus schema validity and the fields the API removed.

Use it for the laptop latency run (status: "Laptop CPU latency") and to confirm a hub serves
the shipped model correctly. Refuses any file in the frozen test manifest (ADR-0022): these
are product checks, never scoring of the frozen sets. Writes aggregates and per-item times
to results/hub/<tag>.json; prints no transcript text and never the key.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.items import BenchItem, read_jsonl  # noqa: E402
from bench.metrics import metric_ratios, score_item  # noqa: E402
from phc_scribe.encounter import Encounter  # noqa: E402

MANIFEST = ROOT / "data" / "bench" / "test-manifest.json"


def frozen_paths() -> set[str]:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {f["path"] for f in m["files"]}


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(q * (len(xs) - 1)))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--items", type=Path, default=ROOT / "data/bench/pilot.20261004.jsonl")
    parser.add_argument("--n", type=int, default=30, help="first N items")
    parser.add_argument("--tag", required=True, help="e.g. laptop-i7 or cloud-4cpu")
    args = parser.parse_args()
    rel = args.items.resolve().relative_to(ROOT).as_posix()
    if rel in frozen_paths():
        raise SystemExit(f"{rel} is a frozen test file: hub checks use dev or pilot items only")
    key = os.environ.get("PHC_API_KEY", "")
    items = list(read_jsonl(args.items, BenchItem))[: args.n]
    import httpx

    client = httpx.Client(
        base_url=args.url,
        timeout=1200,
        trust_env=False,  # a local hub: no proxy
        headers={"Authorization": f"Bearer {key}"},
    )
    rows, scores = [], []
    for it in items:
        t0 = time.perf_counter()
        try:
            r = client.post("/v1/extract", json={"text": it.transcript})
            r.raise_for_status()
            out = r.json()
            pred, removed, error = Encounter.model_validate(out["record"]), out["grounding"], None
        except Exception as e:  # a failed draft counts as schema-invalid, as in the benchmark
            pred, removed, error = None, {"dropped": []}, f"{type(e).__name__}: {str(e)[:120]}"
        secs = round(time.perf_counter() - t0, 1)
        if error and not rows:  # the first draft failed: the hub is not ready, so score nothing
            raise SystemExit(
                f"first request failed ({error}): is the model loaded? Nothing written."
            )
        s = score_item(it.item_id, it.group_id, it.gold, pred)
        scores.append(s)
        rows.append(
            {
                "item_id": it.item_id,
                "seconds": secs,
                "valid": pred is not None,
                "danger_tp": s.danger_tp,
                "danger_fn": s.danger_fn,
                "danger_fp": s.danger_fp,
                "removed_fields": len(removed["dropped"]),
                "error": error,
            }
        )
        print(
            f"{it.item_id}: {secs}s, valid={pred is not None}, danger tp/fn/fp="
            f"{s.danger_tp}/{s.danger_fn}/{s.danger_fp}",
            flush=True,
        )
    warm = [r["seconds"] for r in rows[1:]] or [rows[0]["seconds"]]
    ratios = metric_ratios(scores)
    summary = {
        "tag": args.tag,
        "items": rel,
        "n": len(rows),
        "first_request_s": rows[0]["seconds"],
        "warm_p50_s": statistics.median(warm),
        "warm_p95_s": pct(warm, 0.95),
        "warm_max_s": max(warm),
        "danger_recall": round(ratios["danger_recall"].value(), 4),
        "false_alarm_rate": round(ratios["false_alarm_rate"].value(), 4),
        "schema_valid_rate": round(ratios["schema_valid_rate"].value(), 4),
        "per_item": rows,
    }
    out_path = ROOT / "results" / "hub" / f"{args.tag}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_item"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
