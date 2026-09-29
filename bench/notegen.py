"""Generated ANC visit notes for the supplementary stratum G (ADR-0016).

The gold record is sampled first and the note is rendered from it, so every label is
correct by construction and every evidence quote is verbatim. Rendering is
deterministic given a seed (no LLM in v0). Each item is then verified:

- every evidence quote is located in the note (grounding);
- the rules engine runs on the gold record (flags must be computable);
- the keyword baseline's extra findings (concepts it sees that the gold record does
  not have) are counted, so accidental mentions in fillers surface as a number.

Clinical plausibility comes from simple constraints (e.g. severe-range BP is referred);
the clinical adviser reviews the phrase bank and a random sample of notes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from bench.items import BenchItem
from phc_scribe.encounter import (
    Anc,
    Assertion,
    BloodPressure,
    Count,
    Disposition,
    Encounter,
    Evidence,
    Finding,
    GestationalAge,
    NextVisit,
    Referral,
    Temperature,
    Vitals,
    Weight,
)
from phc_scribe.grounding import locate
from phc_scribe.vocab import load_vocabulary

PHRASES_PATH = Path(__file__).with_name("generate") / "phrases.v0.yaml"
GENERATOR_VERSION = "notegen-v0"

_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th", 7: "7th", 8: "8th"}


@dataclass(frozen=True)
class PhraseBank:
    version: str
    frames: dict[str, list[str]]
    forms: dict[str, list[str]]
    fillers: list[str]


def load_phrase_bank(path: Path = PHRASES_PATH) -> PhraseBank:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    vocab_ids = set(load_vocabulary().ids)
    forms = {cid: list(c["forms"]) for cid, c in data["concepts"].items()}
    unknown = set(forms) - vocab_ids
    if unknown:
        raise ValueError(f"phrase bank has concepts not in the vocabulary: {sorted(unknown)}")
    frames = {k: [f for f in v if "{x}" in f] for k, v in data["frames"].items()}
    # "not {x}" only reads naturally with adjectives; v0 has none, so drop it.
    frames["absent"] = [f for f in frames["absent"] if not f.startswith("not ")]
    return PhraseBank(str(data["version"]), frames, forms, list(data["fillers"]))


@dataclass
class _Parts:
    clauses: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def _ev(text: str) -> Evidence:
    return Evidence(text=text)


def _sample_findings(rng: random.Random, bank: PhraseBank, want_danger: bool) -> list[tuple]:
    vocab = load_vocabulary()
    danger = [c for c in vocab.ids if c in vocab.danger_sign_ids and c in bank.forms]
    other = [c for c in vocab.ids if c not in vocab.danger_sign_ids and c in bank.forms]
    picks: list[tuple[str, str]] = []
    if want_danger:
        picks.append((rng.choice(danger), "present"))
    for _ in range(rng.choice([0, 1, 1, 2])):
        picks.append((rng.choice(other), rng.choice(["present", "present", "absent"])))
    # negated or historical danger signs: the hard cases for extraction
    for _ in range(rng.choice([0, 1, 1, 2])):
        picks.append(
            (rng.choice(danger), rng.choice(["absent", "absent", "historical", "possible"]))
        )
    seen: set[tuple[str, str]] = set()
    concepts_used: set[str] = set()
    out = []
    for concept, assertion in picks:
        # one assertion per concept per note keeps the gold unambiguous in v0
        if (concept, assertion) in seen or concept in concepts_used:
            continue
        seen.add((concept, assertion))
        concepts_used.add(concept)
        out.append((concept, assertion))
    return out


def render_note(rng: random.Random, bank: PhraseBank, want_danger: bool) -> tuple[str, Encounter]:
    """Sample one gold record and render its note. Returns (note, gold)."""
    head: list[str] = []
    gravida = rng.choice([1, 1, 2, 2, 3, 3, 4, 5, 6])
    parity = rng.randint(0, gravida - 1)
    ga_weeks = rng.randint(12, 40)
    # WHO 2016 model: up to 8 contacts; the visit number cannot run ahead of the pregnancy.
    contact = rng.randint(1, max(1, min(8, (ga_weeks - 8) // 4 + 1)))
    anc_kwargs: dict[str, Any] = {}

    visit = "Booking visit." if contact == 1 else f"{_ORDINAL[contact]} ANC visit."
    head.append(visit)
    anc_kwargs["contact_number"] = Count(value=contact, evidence=_ev(visit.rstrip(".")))

    gp = f"G{gravida}P{parity}"
    ga = rng.choice([f"GA {ga_weeks}/40", f"{ga_weeks} weeks gestation", f"EGA {ga_weeks}wks"])
    head.append(f"{gp}, {ga}.")
    anc_kwargs["gravida"] = Count(value=gravida, evidence=_ev(gp))
    anc_kwargs["parity"] = Count(value=parity, evidence=_ev(gp))
    anc_kwargs["gestational_age"] = GestationalAge(weeks=ga_weeks, evidence=_ev(ga))

    findings = _sample_findings(rng, bank, want_danger)
    positive_danger = any(
        a == "present" and c in load_vocabulary().danger_sign_ids for c, a in findings
    )

    # BP: severe range more likely when a danger sign is present (still random).
    band = rng.random()
    if positive_danger and band < 0.35:
        sys_, dia = rng.randint(160, 180), rng.randint(110, 120)
    elif band < 0.25:
        sys_, dia = rng.randint(140, 159), rng.randint(90, 109)
    else:
        sys_, dia = rng.randint(95, 135), rng.randint(60, 85)
    bp = rng.choice([f"BP {sys_}/{dia}", f"BP {sys_}/{dia}mmHg", f"B/P {sys_}/{dia}"])
    vitals: dict[str, Any] = {
        "blood_pressure": BloodPressure(systolic=sys_, diastolic=dia, evidence=_ev(bp))
    }
    vit_clauses = [bp]
    if rng.random() < 0.6:
        t = round(rng.uniform(36.2, 37.4), 1)
        tt = rng.choice([f"T {t}", f"temp {t}°C", f"Temp {t}"])
        vitals["temperature"] = Temperature(value=t, evidence=_ev(tt))
        vit_clauses.append(tt)
    if rng.random() < 0.6:
        w = rng.randint(48, 98)
        wt = rng.choice([f"Wt {w}kg", f"weight {w} kg"])
        vitals["weight"] = Weight(value=w, evidence=_ev(wt))
        vit_clauses.append(wt)

    parts = _Parts()
    for concept, assertion in findings:
        frame = rng.choice(bank.frames[assertion])
        form = rng.choice(bank.forms[concept])
        clause = frame.replace("{x}", form)
        parts.clauses.append(clause)
        parts.findings.append(
            Finding(concept=concept, assertion=Assertion(assertion), evidence=_ev(clause))
        )
    rng.shuffle(parts.clauses)

    body = head[:]
    if parts.clauses:
        body.append("; ".join(parts.clauses) + ".")
    else:
        body.append("No complaints.")
    body.append(", ".join(vit_clauses) + ".")
    body.extend(rng.sample(bank.fillers, k=rng.randint(0, 2)))

    severe_bp = sys_ >= 160 or dia >= 110
    disp: dict[str, Any] = {}
    if positive_danger or severe_bp:
        ref = rng.choice(["Referred to General Hospital", "Referred to FMC", "Refer to CHC"])
        body.append(ref + ".")
        disp["referral"] = Referral(referred=True, evidence=_ev(ref))
    else:
        nxt = rng.choice(["TCA 4/52", "TCA 2/52", "Return in 4 weeks"])
        body.append(nxt + ".")
        disp["next_visit"] = NextVisit(text=nxt, evidence=_ev(nxt))

    note = " ".join(body)
    gold = Encounter(
        findings=parts.findings,
        vitals=Vitals(**vitals),
        anc=Anc(**anc_kwargs),
        disposition=Disposition(**disp),
    )
    return note, gold


class GenReport(BaseModel):
    generator: str = GENERATOR_VERSION
    phrase_bank: str
    seed: int
    items: int = 0
    with_positive_danger: int = 0
    rejected: list[str] = Field(default_factory=list)
    evidence_quotes: int = 0
    evidence_in_baseline_lexicon: int = 0
    baseline_extra_concepts: int = 0


def _evidence_quotes(gold: Encounter) -> list[str]:
    quotes = [f.evidence.text for f in gold.findings if f.evidence]
    for v in (gold.vitals.blood_pressure, gold.vitals.temperature, gold.vitals.weight):
        if v is not None:
            quotes.append(v.evidence.text)
    for c in (gold.anc.gestational_age, gold.anc.gravida, gold.anc.contact_number):
        if c is not None:
            quotes.append(c.evidence.text)
    return quotes


def generate(n: int, seed: int, danger_share: float = 0.4) -> tuple[list[BenchItem], GenReport]:
    from bench.baselines.keyword import extract, load_lexicon
    from phc_scribe.rules import check
    from phc_scribe.text import fold_text

    bank = load_phrase_bank()
    lex = load_lexicon()
    rng = random.Random(seed)  # noqa: S311 (data generation, not security)
    report = GenReport(phrase_bank=bank.version, seed=seed)
    items: list[BenchItem] = []
    k = 0
    while len(items) < n:
        k += 1
        want_danger = rng.random() < danger_share
        note, gold = render_note(rng, bank, want_danger)
        item_id = f"g-{seed}-{k:04d}"
        missing = [q for q in _evidence_quotes(gold) if locate(note, q) is None]
        if missing:
            report.rejected.append(f"{item_id}: evidence not found {missing}")
            continue
        check(gold)  # must not raise
        base_concepts = {str(f.concept) for f in extract(note).findings}
        gold_concepts = {str(f.concept) for f in gold.findings}
        report.baseline_extra_concepts += len(base_concepts - gold_concepts)
        for f in gold.findings:
            report.evidence_quotes += 1
            pat = lex.concepts.get(str(f.concept))
            if f.evidence and pat is not None and pat.search(fold_text(f.evidence.text)):
                report.evidence_in_baseline_lexicon += 1
        if any(
            f.assertion == Assertion.present and str(f.concept) in load_vocabulary().danger_sign_ids
            for f in gold.findings
        ):
            report.with_positive_danger += 1
        items.append(
            BenchItem(
                item_id=item_id,
                group_id=item_id,
                stratum="G",
                language="en",
                origin="generated",
                transcript=note,
                gold=gold,
            )
        )
    report.items = len(items)
    return items, report
