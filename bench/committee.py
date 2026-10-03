"""Committee pre-labelling and risk-based human sampling for the counted benchmark (ADR-0025).

    python -m bench.committee fetch --targets data/asr/targets.v1.jsonl \
        --out committee.items.jsonl                                   # on Kaggle
    python -m bench.committee triage --queue data/private/label_queue.s4w.jsonl \
        --pred qwen3.jsonl --pred gemma3.jsonl --pred mistral.jsonl \
        --out-dir data/private/committee                              # on the laptop

`fetch` rebuilds the 600 test-pool items from public clip ids: it reads only the text
columns of WazobiaSpeech `dev` + `dev_test` (no audio), with a placeholder gold. The three
committee members then label them with the same prompt, constrained decoding and grounding
as every evaluated system (bench.runners.llm).

`triage` applies the rules ADR-0025 fixed before the committee ran:
- **Stratum A (human review):** a member's output is invalid or loses a field in grounding;
  or a member reports a danger sign (present or possible); or the members disagree on the
  scored content: the set of (concept, assertion) findings, blood pressure or gestational
  age.
- **Stratum B (consensus):** all three valid, grounded, identical on that content, and no
  danger sign.
- **Committee gold:** field by field, the answer at least two of the three members give
  (findings by (concept, assertion); vitals, ANC counts, tests, medications and
  disposition by value). Evidence comes from the first member, in fixed order, that gave it.
- **Human sample:** a seeded random 120 from A and 60 from B (all of a stratum if smaller),
  with 20% of the sample double-labelled. Drawn before anyone labels; never shown the
  committee's answers.

Writes the committee gold, the triage table and the sample's label queue. Prints counts only.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from bench.items import BenchItem, Language, Prediction, read_jsonl, write_jsonl
from phc_scribe.encounter import POSITIVE_ASSERTIONS, Assertion, Encounter
from phc_scribe.grounding import ground
from phc_scribe.vocab import load_vocabulary

SEED = 20261009  # differs from every other seed in the repo
SAMPLE = {"A": 120, "B": 60}
DOUBLE_SHARE = 0.2
QUORUM = 2  # of 3 members

# Members (ADR-0025): three families, none of them Llama-3.1 (the training-label teacher)
# or N-ATLaS (the system under test). Pre-quantised 4-bit copies so each fits a Kaggle T4
# pair; revisions pinned 3 Oct 2026. Phi-4 replaced Gemma-3-12B after the 3 Oct smoke run:
# a T4 has no native bfloat16, and Gemma 3 overflows in float16 (ADR-0025, amendment).
# name -> (repo, revision, batch size); the 24B model needs smaller batches on a T4.
MEMBERS: dict[str, tuple[str, str, int]] = {
    "qwen3-14b": ("unsloth/Qwen3-14B-bnb-4bit", "b455922269e4678c84f854fe38a6993d73614a1e", 8),
    "phi-4-14b": ("unsloth/phi-4-bnb-4bit", "098ea917f967c8811e6f579cc38872b2bf3d4bf4", 8),
    "mistral-small-24b": (
        "unsloth/Mistral-Small-24B-Instruct-2501-bnb-4bit",
        "cb4e166b818799cd769592eed8f7142ceab779ca",
        4,
    ),
}


@dataclass(frozen=True)
class Vote:
    """One member's answer on one item, after grounding."""

    valid: bool
    grounded: bool
    record: Encounter | None
    pairs: frozenset[tuple[str, str]] = frozenset()
    danger: frozenset[str] = frozenset()
    bp: tuple[int, int] | None = None
    ga: int | None = None

    @property
    def usable(self) -> bool:
        return self.valid and self.grounded

    def content(self) -> tuple:
        return (self.pairs, self.bp, self.ga)


@dataclass
class Triage:
    item_id: str
    stratum: str  # "A" or "B"
    reasons: list[str] = field(default_factory=list)
    sampled: bool = False
    double: bool = False


class TriageReport(BaseModel):
    items: int = 0
    stratum_a: int = 0
    stratum_b: int = 0
    reasons: dict[str, int] = {}
    sampled_a: int = 0
    sampled_b: int = 0
    double_labelled: int = 0
    gold_with_findings: int = 0
    gold_with_danger: int = 0
    member_valid: dict[str, int] = {}
    member_grounded: dict[str, int] = {}


def vote(pred: Prediction | None, transcript: str, danger_ids: frozenset[str]) -> Vote:
    if pred is None or pred.record is None:
        return Vote(valid=False, grounded=False, record=None)
    g = ground(pred.record, transcript)
    rec = g.record
    bp = rec.vitals.blood_pressure
    ga = rec.anc.gestational_age
    return Vote(
        valid=True,
        grounded=not g.dropped,
        record=rec,
        pairs=frozenset(
            (str(f.concept), str(f.assertion))
            for f in rec.findings
            if f.assertion != Assertion.not_mentioned
        ),
        danger=frozenset(
            str(f.concept)
            for f in rec.findings
            if str(f.concept) in danger_ids and f.assertion in POSITIVE_ASSERTIONS
        ),
        bp=(bp.systolic, bp.diastolic) if bp else None,
        ga=ga.weeks if ga else None,
    )


def stratum_of(votes: Sequence[Vote]) -> tuple[str, list[str]]:
    reasons = []
    if any(not v.valid for v in votes):
        reasons.append("invalid")
    if any(v.valid and not v.grounded for v in votes):
        reasons.append("ungrounded")
    if any(v.danger for v in votes):
        reasons.append("danger")
    if len({v.content() for v in votes if v.valid}) > 1:
        reasons.append("disagree")
    return ("A" if reasons else "B"), reasons


def _key(obj: BaseModel) -> str:
    return json.dumps(obj.model_dump(mode="json", exclude={"evidence"}), sort_keys=True)


def _majority(candidates: Sequence[BaseModel | None]) -> BaseModel | None:
    """The value at least QUORUM members give (evidence ignored); first giver's copy."""
    counts = Counter(_key(c) for c in candidates if c is not None)
    for c in candidates:
        if c is not None and counts[_key(c)] >= QUORUM:
            return c
    return None


def _majority_list(lists: Sequence[Sequence[BaseModel]]) -> list:
    counts = Counter(k for lst in lists for k in {_key(x) for x in lst})
    out, seen = [], set()
    for lst in lists:
        for x in lst:
            k = _key(x)
            if counts[k] >= QUORUM and k not in seen:
                seen.add(k)
                out.append(x)
    return out


def majority_record(records: Sequence[Encounter]) -> Encounter:
    """Committee gold: field by field, what at least QUORUM members say."""
    v = [r.vitals for r in records]
    a = [r.anc for r in records]
    d = [r.disposition for r in records]
    findings = [
        f
        for f in _majority_list([r.findings for r in records])
        if f.assertion != Assertion.not_mentioned
    ]
    return Encounter.model_validate(
        {
            "findings": [f.model_dump(mode="json") for f in findings],
            "vitals": {
                name: (m.model_dump(mode="json") if m else None)
                for name in ("blood_pressure", "temperature", "weight", "pulse")
                for m in [_majority([getattr(x, name) for x in v])]
            },
            "anc": {
                **{
                    name: (m.model_dump(mode="json") if m else None)
                    for name in ("gestational_age", "gravida", "parity", "contact_number")
                    for m in [_majority([getattr(x, name) for x in a])]
                },
                "tests": [t.model_dump(mode="json") for t in _majority_list([x.tests for x in a])],
                "medications": [
                    m.model_dump(mode="json") for m in _majority_list([x.medications for x in a])
                ],
            },
            "disposition": {
                name: (m.model_dump(mode="json") if m else None)
                for name in ("referral", "next_visit")
                for m in [_majority([getattr(x, name) for x in d])]
            },
        }
    )


def draw_sample(triage: list[Triage], seed: int = SEED) -> None:
    """Seeded random sample within each stratum; 20% of it double-labelled. In place."""
    rng = random.Random(seed)  # noqa: S311 (sampling, not security)
    picked: list[Triage] = []
    for stratum, n in SAMPLE.items():
        pool = sorted((t for t in triage if t.stratum == stratum), key=lambda t: t.item_id)
        rng.shuffle(pool)
        for t in pool[:n]:
            t.sampled = True
            picked.append(t)
    picked.sort(key=lambda t: t.item_id)
    rng.shuffle(picked)
    for t in picked[: round(len(picked) * DOUBLE_SHARE)]:
        t.double = True


def triage_items(
    items: Sequence[BenchItem], preds: dict[str, dict[str, Prediction]], seed: int = SEED
) -> tuple[list[BenchItem], list[Triage], TriageReport]:
    """Strata, committee gold and the human sample. `preds`: member -> item_id -> prediction."""
    danger_ids = load_vocabulary().danger_sign_ids
    members = list(preds)
    report = TriageReport(items=len(items))
    report.member_valid = dict.fromkeys(members, 0)
    report.member_grounded = dict.fromkeys(members, 0)
    reasons: Counter[str] = Counter()
    gold_items, triage = [], []
    for item in items:
        votes = [vote(preds[m].get(item.item_id), item.transcript, danger_ids) for m in members]
        for m, v in zip(members, votes, strict=True):
            report.member_valid[m] += v.valid
            report.member_grounded[m] += v.usable
        stratum, why = stratum_of(votes)
        reasons.update(why)
        usable = [v.record for v in votes if v.usable and v.record is not None]
        gold = majority_record(usable) if len(usable) >= QUORUM else Encounter()
        gold_items.append(item.model_copy(update={"gold": gold}))
        triage.append(Triage(item.item_id, stratum, why))
        report.gold_with_findings += bool(gold.findings)
        report.gold_with_danger += any(
            str(f.concept) in danger_ids and f.assertion in POSITIVE_ASSERTIONS
            for f in gold.findings
        )
    draw_sample(triage, seed)
    report.stratum_a = sum(t.stratum == "A" for t in triage)
    report.stratum_b = sum(t.stratum == "B" for t in triage)
    report.reasons = dict(sorted(reasons.items()))
    report.sampled_a = sum(t.sampled and t.stratum == "A" for t in triage)
    report.sampled_b = sum(t.sampled and t.stratum == "B" for t in triage)
    report.double_labelled = sum(t.double for t in triage)
    return gold_items, triage, report


def fetch_items(targets: list[dict]) -> list[BenchItem]:
    """Test-pool items from public clip ids (text columns of dev + dev_test only)."""
    from bench.wazobia import read_health_rows

    out: list[BenchItem] = []
    for lang in sorted({t["language"] for t in targets if t["split"] == "dev_pool"}):
        wanted = {
            t["audio_id"] for t in targets if t["split"] == "dev_pool" and t["language"] == lang
        }
        language: Language = lang
        rows = [r for s in ("dev", "dev_test") for r in read_health_rows(language, s)]
        seen: set[str] = set()
        for r in rows:
            if r.source_id in wanted and r.source_id not in seen:
                seen.add(r.source_id)
                out.append(
                    BenchItem(
                        item_id=f"s4w-{lang}-{r.source_id}",
                        group_id=f"wazobia:{r.speaker_id}",
                        stratum="S4W",
                        language=language,
                        origin="real",
                        transcript=r.transcript,
                        gold=Encounter(),
                    )
                )
        print(f"committee items {lang}: {len(seen)} of {len(wanted)} clips found", flush=True)
    return sorted(out, key=lambda i: i.item_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--targets", type=Path, required=True)
    f.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("triage")
    t.add_argument("--queue", type=Path, required=True, help="the test pool's label queue")
    t.add_argument("--pred", type=Path, action="append", required=True, help="one per member")
    t.add_argument("--out-dir", type=Path, required=True)
    t.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    if args.cmd == "fetch":
        targets = [
            json.loads(x) for x in args.targets.read_text(encoding="utf-8").splitlines() if x
        ]
        items = fetch_items(targets)
        write_jsonl(args.out, items)
        print(f"committee items: {len(items)} -> {args.out}")
        return 0

    queue = [
        json.loads(x) for x in args.queue.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    items = [
        BenchItem(
            item_id=q["item_id"],
            group_id=q["group_id"],
            stratum="S4W",
            language=q["language"],
            origin="real",
            transcript=q["transcript"],
            gold=Encounter(),
        )
        for q in queue
    ]
    if len(args.pred) != len(MEMBERS):
        parser.error(f"need one --pred per member ({len(MEMBERS)})")
    preds: dict[str, dict[str, Prediction]] = {}
    for path in args.pred:
        rows = list(read_jsonl(path, Prediction))
        name = rows[0].system if rows else path.stem
        preds[name] = {p.item_id: p for p in rows}
    missing = {m: sum(i.item_id not in p for i in items) for m, p in preds.items()}
    if any(missing.values()):
        print(f"warning: predictions missing per member: {missing}", flush=True)
    gold_items, triage, report = triage_items(items, preds, args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out_dir / "committee.gold.jsonl", gold_items)
    with (args.out_dir / "committee.triage.jsonl").open("w", encoding="utf-8") as fh:
        for row in triage:
            fh.write(json.dumps(row.__dict__) + "\n")
    by_id = {t.item_id: t for t in triage}
    sample = [
        {**q, "double": by_id[q["item_id"]].double} for q in queue if by_id[q["item_id"]].sampled
    ]
    with (args.out_dir / "label_queue.committee-sample.jsonl").open("w", encoding="utf-8") as fh:
        for q in sample:
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"=== COMMITTEE {json.dumps(report.model_dump())}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
