"""scripts/label_report.py: counts only, latest label wins, agreement on danger signs."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from label_report import kappa, report  # noqa: E402


def lab(item, who, concepts=(), status="labelled", at="2026-10-08T10:00:00Z", ms=30_000):
    return {
        "item_id": item,
        "status": status,
        "findings": [
            {"concept": c, "assertion": "present", "evidence": {"text": "SECRET TRANSCRIPT"}}
            for c in concepts
        ],
        "labeller": who,
        "labelled_at": at,
        "elapsed_ms": ms,
    }


def test_kappa():
    assert kappa([(True, True), (False, False)]) == 1.0
    assert kappa([(True, False), (False, True)]) == -1.0
    assert kappa([]) is None


def test_report_counts_agreement_and_gold():
    labels = [
        lab("a", "malik", ["vaginal_bleeding"]),
        lab("a", "rahmat", ["vaginal_bleeding"]),
        lab("b", "malik", []),
        lab("b", "rahmat", ["fever"]),
        lab("c", "malik", [], status="skip"),
        lab("d", "rahmat", ["convulsions"], at="2026-10-08T09:00:00Z"),
        lab("d", "rahmat", [], at="2026-10-08T11:00:00Z"),  # relabel replaces
        lab("e", "malik", ["headache"]),  # not a danger sign
    ]
    gold = [lab("a", "gold:agreed", ["vaginal_bleeding"]), lab("b", "gold:clinician", ["fever"])]
    r = report(labels, gold)
    assert r["labellers"]["malik"] == {
        "labelled": 3,
        "skipped": 1,
        "with_danger_sign": 1,
        "median_seconds": 30.0,
    }
    assert r["labellers"]["rahmat"]["with_danger_sign"] == 2  # d was relabelled to none
    assert r["agreement"]["malik + rahmat"]["agree_any_danger_sign"] == "1/2"
    assert r["gold"]["settled_by"] == {"agreed": 1, "clinician": 1}
    assert r["gold"]["danger_signs"] == {"vaginal_bleeding": 1, "fever": 1}


def test_prints_no_transcript_text(tmp_path):
    f = tmp_path / "labels.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in [lab("a", "m", ["fever"]), lab("a", "r", [])]))
    out = subprocess.run(  # noqa: S603 (our own script, fixed arguments)
        [sys.executable, str(ROOT / "scripts" / "label_report.py"), str(f)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "SECRET" not in out
    assert json.loads(out)["items_labelled_by_2_or_more"] == 1
