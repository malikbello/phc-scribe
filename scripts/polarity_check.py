"""Measure the polarity check (ADR-0030) on development data only.

    python scripts/polarity_check.py

Three dev sources, none in the frozen test manifest (ADR-0022; frozen files are refused):
1. **Gold findings** of the pilot items and of the draft rare-sign phrasebank: a flag on a
   gold present/possible/historical finding is a *false flag* (the recall risk); a gold
   *absent* quote given as "present" should be flagged (the *catch rate*: what the check
   would do with the model's commonest assertion error).
2. **Saved model predictions** on the pilot items (every run under results/modal): each
   flagged prediction is checked against gold (same concept and assertion = correct).

Writes results/polarity/dev.<date>.json; prints counts and the flagged quotes (dev text only).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from phc_scribe.polarity import reads_opposite  # noqa: E402

MANIFEST = ROOT / "data" / "bench" / "test-manifest.json"
PILOT = ROOT / "data" / "bench" / "pilot.20261004.jsonl"
PHRASEBANK = ROOT / "data" / "train" / "phrasebank.rare.v0.yaml"


def refuse_frozen(*paths: Path) -> None:
    frozen = {f["path"] for f in json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]}
    for p in paths:
        if p.resolve().relative_to(ROOT).as_posix() in frozen:
            raise SystemExit(
                f"{p} is a frozen test file: the polarity check is developed on dev data only"
            )


def gold_findings() -> list[dict]:
    out = []
    for line in PILOT.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        for f in item["gold"]["findings"]:
            out.append(
                {
                    "source": "pilot",
                    "concept": f["concept"],
                    "assertion": f["assertion"],
                    "quote": f["evidence"]["text"],
                }
            )
    for e in yaml.safe_load(PHRASEBANK.read_text(encoding="utf-8"))["entries"]:
        out.append(
            {
                "source": f"phrasebank-{e['language']}",
                "concept": e["concept"],
                "assertion": e["assertion"],
                "quote": e["evidence"],
            }
        )
    return out


def main() -> int:
    preds = sorted((ROOT / "results" / "modal").glob("*/pilot*.pred.jsonl"))
    refuse_frozen(PILOT, PHRASEBANK, *preds)
    report: dict = {
        "date": date.today().isoformat(),
        "dev_sources": [str(p.relative_to(ROOT)) for p in [PILOT, PHRASEBANK, *preds]],
    }

    golds = gold_findings()
    positive = [g for g in golds if g["assertion"] != "absent"]
    absent = [g for g in golds if g["assertion"] == "absent"]
    false_flags = [g for g in positive if reads_opposite(g["concept"], g["assertion"], g["quote"])]
    caught = [g for g in absent if reads_opposite(g["concept"], "present", g["quote"])]
    report["gold"] = {
        "positive_findings": len(positive),
        "false_flags": len(false_flags),
        "false_flag_quotes": false_flags,
        "absent_findings": len(absent),
        "absent_quotes_flagged_if_marked_present": len(caught),
        "missed_absent_quotes": [g for g in absent if g not in caught],
    }

    gold_by_item = {
        json.loads(line)["item_id"]: {
            (f["concept"], f["assertion"]) for f in json.loads(line)["gold"]["findings"]
        }
        for line in PILOT.read_text(encoding="utf-8").splitlines()
    }
    runs = {}
    for path in preds:
        flagged, right, wrong_unflagged, total = [], 0, 0, 0
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            record = row.get("record") or {}
            for f in record.get("findings", []) or []:
                if f.get("assertion") in ("absent", "not_mentioned") or not f.get("evidence"):
                    continue
                total += 1
                correct = (f["concept"], f["assertion"]) in gold_by_item.get(row["item_id"], set())
                cue = reads_opposite(f["concept"], f["assertion"], f["evidence"]["text"])
                if cue:
                    flagged.append(
                        {
                            "item_id": row["item_id"],
                            "concept": f["concept"],
                            "assertion": f["assertion"],
                            "quote": f["evidence"]["text"],
                            "cue": cue,
                            "gold_agrees": correct,
                        }
                    )
                    right += not correct
                elif not correct:
                    wrong_unflagged += 1
        runs[str(path.relative_to(ROOT))] = {
            "non_absent_predictions": total,
            "flagged": len(flagged),
            "flagged_and_wrong": right,
            "wrong_but_not_flagged": wrong_unflagged,
            "flags": flagged,
        }
    report["predictions"] = runs

    out = ROOT / "results" / "polarity" / f"dev.{date.today():%Y%m%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    g = report["gold"]
    print(
        f"gold: {g['false_flags']}/{g['positive_findings']} false flags on real findings; "
        f"{g['absent_quotes_flagged_if_marked_present']}/{g['absent_findings']} "
        "denials would be caught"
    )
    for q in g["false_flag_quotes"]:
        print("  FALSE FLAG:", q)
    for name, r in runs.items():
        print(
            f"{name}: {r['flagged']} flagged of {r['non_absent_predictions']}; "
            f"{r['flagged_and_wrong']} of those wrong by gold; "
            f"{r['wrong_but_not_flagged']} other wrong predictions"
        )
        for f in r["flags"]:
            print("   ", f)
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
