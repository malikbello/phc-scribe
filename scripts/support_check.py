"""Measure the support check (ADR-0036) on development data only.

    python scripts/support_check.py

The concept word lists were written from the training set; this script measures them there
and on data they were not written from. Every source is outside the frozen test manifest
(ADR-0022; frozen files are refused):
1. **Gold findings** (present, possible or historical danger signs): a flag on one is a
   *false flag*, the cost the check puts on the health worker. Sources: the training set and
   the held-out dev items (data/private, counts only), the pilot items and the rare-sign
   phrasebank (committed, quotes listed).
2. **Saved model predictions** on the pilot and dev items (every run under results/modal):
   each flag is checked against gold (same concept and assertion = the model was right).
   Measurements: a predicted vital whose quote has no number, and whether gold has it.

Writes results/support/dev.<date>.json; private text is counted, never written.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from phc_scribe.support import CONCEPT_WORDS, has_number, mentions  # noqa: E402

MANIFEST = ROOT / "data" / "bench" / "test-manifest.json"
PILOT = ROOT / "data" / "bench" / "pilot.20261004.jsonl"
PHRASEBANK = ROOT / "data" / "train" / "phrasebank.rare.v0.yaml"
TRAIN = ROOT / "data" / "private" / "train" / "sft.v1.jsonl"
DEV = ROOT / "data" / "private" / "train" / "sft.v1.dev.items.jsonl"
CHECKED = set(CONCEPT_WORDS)
VITALS = ("blood_pressure", "temperature", "weight", "pulse")


def refuse_frozen(*paths: Path) -> None:
    frozen = {f["path"] for f in json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]}
    for p in paths:
        if p.resolve().relative_to(ROOT).as_posix() in frozen:
            raise SystemExit(
                f"{p} is a frozen test file: the support check is developed on dev data only"
            )


def _positive(findings: list[dict]) -> list[tuple[str, str]]:
    return [
        (f["concept"], f["evidence"]["text"])
        for f in findings
        if f["concept"] in CHECKED and f["assertion"] not in ("absent", "not_mentioned")
    ]


def gold_sources() -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {"pilot": [], "phrasebank": []}
    for line in PILOT.read_text(encoding="utf-8").splitlines():
        out["pilot"] += _positive(json.loads(line)["gold"]["findings"])
    for e in yaml.safe_load(PHRASEBANK.read_text(encoding="utf-8"))["entries"]:
        if e["concept"] in CHECKED and e["assertion"] != "absent":
            out["phrasebank"].append((e["concept"], e["evidence"]))
    # Private items by origin: "generated" (written for training) or "real" (speech
    # transcripts whose labels came from a teacher model and are noisier).
    if TRAIN.exists():
        for line in TRAIN.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            record = json.loads(row["messages"][-1]["content"])
            key = f"train (private, {row['origin']})"
            out.setdefault(key, []).extend(_positive(record.get("findings", [])))
    if DEV.exists():
        for line in DEV.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            key = f"dev (private, {row['origin']})"
            out.setdefault(key, []).extend(_positive(row["gold"]["findings"]))
    return out


def gold_items() -> dict[str, dict]:
    items = {}
    for path in (PILOT, DEV):
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                items[row["item_id"]] = row["gold"]
    return items


def main() -> int:
    preds = sorted((ROOT / "results" / "modal").glob("*/*.pred.jsonl"))
    refuse_frozen(PILOT, PHRASEBANK, TRAIN, DEV, *preds)
    report: dict = {
        "date": date.today().isoformat(),
        "dev_sources": [
            str(p.relative_to(ROOT)) for p in [PILOT, PHRASEBANK, TRAIN, DEV, *preds] if p.exists()
        ],
    }

    report["gold"] = {}
    for name, rows in gold_sources().items():
        flagged = [(c, q) for c, q in rows if not mentions(c, q)]
        entry: dict = {"danger_findings": len(rows), "false_flags": len(flagged)}
        if "private" not in name:
            entry["false_flag_quotes"] = [{"concept": c, "quote": q} for c, q in flagged]
        report["gold"][name] = entry

    golds = gold_items()
    runs = {}
    for path in preds:
        n, flags, flagged_wrong, vitals, vitals_flagged, vitals_flagged_wrong = 0, [], 0, 0, 0, 0
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            gold = golds.get(row["item_id"])
            record = row.get("record") or {}
            if gold is None:
                continue
            truth = {(f["concept"], f["assertion"]) for f in gold["findings"]}
            for f in record.get("findings", []) or []:
                if f.get("concept") not in CHECKED or not f.get("evidence"):
                    continue
                if f.get("assertion") in ("absent", "not_mentioned"):
                    continue
                n += 1
                if not mentions(f["concept"], f["evidence"]["text"]):
                    right = (f["concept"], f["assertion"]) in truth
                    flagged_wrong += not right
                    flag = {
                        "item_id": row["item_id"],
                        "concept": f["concept"],
                        "gold_agrees": right,
                    }
                    if row["item_id"].startswith("pilot-"):  # committed pilot text only
                        flag["quote"] = f["evidence"]["text"]
                    flags.append(flag)
            for v in VITALS:
                m = (record.get("vitals") or {}).get(v)
                if not m or not m.get("evidence"):
                    continue
                vitals += 1
                if not has_number(m["evidence"]["text"]):
                    vitals_flagged += 1
                    vitals_flagged_wrong += not (gold.get("vitals") or {}).get(v)
        runs[str(path.relative_to(ROOT))] = {
            "danger_predictions": n,
            "flagged": len(flags),
            "flagged_and_wrong_by_gold": flagged_wrong,
            "vitals_predicted": vitals,
            "vitals_flagged": vitals_flagged,
            "vitals_flagged_and_not_in_gold": vitals_flagged_wrong,
            "flags": flags,
        }
    report["predictions"] = runs

    out = ROOT / "results" / "support" / f"dev.{date.today():%Y%m%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, g in report["gold"].items():
        print(f"gold {name}: {g['false_flags']}/{g['danger_findings']} false flags")
        for q in g.get("false_flag_quotes", []):
            print("  FALSE FLAG:", q)
    for name, r in runs.items():
        print(
            f"{name}: {r['flagged']}/{r['danger_predictions']} danger findings flagged, "
            f"{r['flagged_and_wrong_by_gold']} of them wrong by gold; vitals "
            f"{r['vitals_flagged']}/{r['vitals_predicted']} flagged, "
            f"{r['vitals_flagged_and_not_in_gold']} of them not in gold"
        )
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
