"""Build the clinical adviser's review pack (HTML, printable to PDF) from the repo files.

    python scripts/build_review_pack.py --out review_pack.html

One document covering what needs clinical sign-off before gold labels count:
the finding vocabulary, the danger-sign rules, the generated-note phrase bank and the
open questions in docs/annotation-guidelines.md section 9. Built from the source
files, so the pack never drifts from what the code uses.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from phc_scribe.vocab import load_vocabulary  # noqa: E402

RULES = ROOT / "rules" / "danger_signs.v0.yaml"
PHRASES = ROOT / "bench" / "generate" / "phrases.v0.yaml"
GUIDELINES = ROOT / "docs" / "annotation-guidelines.md"

CSS = """
body{font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#1d1d1b;
 background:#fff;margin:0;padding:16px;max-width:820px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:18px;margin:28px 0 8px;border-bottom:2px solid #1f6f5c}
.meta{color:#6b6b66;font-size:13px}table{border-collapse:collapse;width:100%;margin:8px 0}
th,td{border:1px solid #deded8;padding:6px;vertical-align:top;text-align:left;font-size:14px}
th{background:#f2f2ee}.ok{white-space:nowrap}.box{display:inline-block;width:14px;height:14px;
 border:1.5px solid #555;border-radius:3px;margin-right:4px;vertical-align:-2px}
.note{height:34px}.ds{color:#a4302a;font-weight:600}code{font-size:13px}
@media print{h2{break-after:avoid}tr{break-inside:avoid}}
"""


def esc(x: Any) -> str:
    return html.escape(str(x))


VITAL_LABELS = {
    "bp_systolic": "systolic BP",
    "bp_diastolic": "diastolic BP",
    "temperature_c": "temperature (°C)",
    "pulse": "pulse",
    "weight_kg": "weight (kg)",
}
TEST_LABELS = {"haemoglobin": "Hb (g/dL)", "pcv": "PCV (%)", "urine_protein": "urine protein"}
OPS = {"gte": "≥", "gt": ">", "lte": "≤", "lt": "<"}


def _measure(spec: dict[str, Any], labels: dict[str, str]) -> str:
    name = labels.get(spec["name"], str(spec["name"]).replace("_", " "))
    if "in" in spec:
        return f"{esc(name)} is {esc(' or '.join(map(str, spec['in'])))}"
    parts = [f"{esc(name)} {OPS[k]} {esc(v)}" for k, v in spec.items() if k in OPS]
    return " and ".join(parts) or esc(name)


def condition(c: Any, labels: dict[str, str]) -> str:
    """Readable form of a rule condition."""
    if isinstance(c, dict):
        if "finding" in c:
            return f"<b>{esc(labels.get(c['finding'], c['finding']))}</b> (present or possible)"
        if "vital" in c:
            return _measure(c["vital"], VITAL_LABELS)
        if "test" in c:
            return _measure(c["test"], TEST_LABELS)
        for op in ("all", "any"):
            if op in c:
                joiner = " <b>AND</b> " if op == "all" else " or "
                return "(" + joiner.join(condition(x, labels) for x in c[op]) + ")"
    return esc(c)


def tick() -> str:
    return "<span class=box></span>OK <span class=box></span>Change"


def build() -> str:
    vocab = load_vocabulary()
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    phrases = yaml.safe_load(PHRASES.read_text(encoding="utf-8"))
    guide = GUIDELINES.read_text(encoding="utf-8")
    m = re.search(r"## 9\. Open questions.*?\n(.*?)(?:\n## |\Z)", guide, re.S)
    questions = re.findall(r"^\d+\.\s+(.*)$", m.group(1), re.M) if m else []

    out = [
        f"<!doctype html><html><head><meta charset=utf-8><title>Clinical review pack</title>"
        f"<meta name=viewport content='width=device-width,initial-scale=1'><style>{CSS}</style>"
        "</head><body>"
    ]
    out.append("<h1>PHC Scribe: clinical review pack</h1>")
    out.append(
        f"<p class=meta>Prepared {dt.date.today():%d %b %Y}. About 90 minutes. Mark each "
        "row OK or Change and write the change in the Note column. Nothing here is used "
        "for patient care; it defines how the benchmark is scored.</p>"
    )

    out.append(
        "<h2>1. Open questions (please answer)</h2><table><tr><th>#</th><th>Question</th>"
        "<th style='width:40%'>Your answer</th></tr>"
    )
    for i, q in enumerate(questions, 1):
        out.append(f"<tr><td>{i}</td><td>{esc(q)}</td><td class=note></td></tr>")
    out.append("</table>")

    out.append(
        "<h2>2. Findings list (danger signs first)</h2><table><tr><th>Finding</th>"
        "<th>Definition</th><th class=ok>Check</th><th>Note</th></tr>"
    )
    for c in sorted(vocab.concepts, key=lambda c: (not c.danger_sign, c.label_en)):
        label = f"<span class=ds>{esc(c.label_en)}</span>" if c.danger_sign else esc(c.label_en)
        out.append(
            f"<tr><td>{label}</td><td>{esc(c.definition)}</td><td class=ok>{tick()}</td>"
            "<td class=note></td></tr>"
        )
    out.append("</table>")

    labels = {c.id: c.label_en for c in vocab.concepts}
    sev = {s["id"] if isinstance(s, dict) else s: s for s in rules.get("severities", [])}
    out.append(
        "<h2>3. Danger-sign rules</h2><p class=meta>Each rule fires on the record. "
        "<i>Present or possible</i> fires; <i>absent</i> and <i>past pregnancy</i> do not. "
        "The action text is what the health worker sees.</p>"
        "<table><tr><th>Rule</th><th>Fires when</th><th>Action shown</th>"
        "<th class=ok>Check</th><th>Note</th></tr>"
    )
    for r in rules["rules"]:
        level = r.get("severity", "")
        level = (
            sev.get(level, {}).get("label_en", level) if isinstance(sev.get(level), dict) else level
        )
        out.append(
            f"<tr><td><b>{esc(r['id'])}</b> {esc(r['name'])}</td><td>{condition(r['when'], labels)}"
            f"</td><td>{esc(r.get('message_en', ''))}<br><span class=meta>{esc(level)}"
            f"</span></td><td class=ok>{tick()}</td><td class=note></td></tr>"
        )
    out.append("</table>")

    out.append(
        "<h2>4. How generated notes phrase each finding</h2><p class=meta>These wordings "
        "build the practice notes. Cross out anything a Nigerian PHC worker would not write; "
        "add common local wordings.</p><table><tr><th>Finding</th><th>Wordings</th>"
        "<th class=ok>Check</th><th>Note</th></tr>"
    )
    for cid, spec in phrases["concepts"].items():
        c = vocab.get(cid)
        label = f"<span class=ds>{esc(c.label_en)}</span>" if c.danger_sign else esc(c.label_en)
        out.append(
            f"<tr><td>{label}</td><td>{esc('; '.join(spec['forms']))}</td>"
            f"<td class=ok>{tick()}</td><td class=note></td></tr>"
        )
    out.append(
        "</table><p class=meta>Sentence patterns: "
        + esc(" · ".join(f for fs in phrases["frames"].values() for f in fs))
        + "</p>"
    )
    out.append("<h2>Sign-off</h2><p>Name: ______________________ &nbsp; Date: ____________</p>")
    out.append("</body></html>")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(build(), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
