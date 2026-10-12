"""Support check: a kept value whose own quote does not say it (ADR-0036).

Grounding proves a quote is in the transcript; the polarity check (ADR-0030) reads it for the
opposite. Neither notices a quote about something else. In the end-to-end test on the laptop
hub (12 Oct 2026) the shipped model drafted ``severe_headache: present`` with the quote "the
baby moved well no fever the bps 120 over 80 ..." (the headache was said, one sentence
earlier), and a temperature of 37 °C from "no fever". Two narrow checks:

1. **Concept words.** A danger-sign finding whose quote has none of the concept's words in
   English, Pidgin or Yoruba ("bleed", "blood", "spotting", "ẹ̀jẹ̀"). "Looks very ill" is a
   general impression with no fixed words, so it is not checked.
2. **A number.** A measurement whose quote has no number at all, as digits or as words.

Like the polarity check, a hit only **flags** the value for the health worker; nothing is
dropped or changed, so no reported metric moves. The word lists are wide on purpose: a miss
costs one unflagged error, a false flag costs a nurse's attention on every visit. They were
written from the training set and checked on dev data (scripts/support_check.py). Matching
runs on folded text (no tone marks or dots below, lower case; phc_scribe.text).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from phc_scribe.encounter import Assertion, Encounter
from phc_scribe.text import fold_text

# Word starts per danger sign. English and Pidgin share most words; Yoruba stems are folded.
_WORDS: dict[str, str] = {
    "vaginal_bleeding": r"bleed|bled|blood|spot|haemorrh|hemorrh|clot|period|menstru|pv\b"
    r"|per vagina|eje\b|e je\b|seje",
    "convulsions": r"convuls|fit\b|fits\b|seiz|jerk|shak|shook|tremb|epilep|eclamp|warapa|giri"
    r"|gbon|subu|fell\b|fall",
    "severe_headache": r"head|migrain|ori\b|ori-|orififo",
    "blurred_vision": r"vision|visual|see\b|seeing|saw\b|seen\b|sight|blur|eye|unclear|clear"
    r"|dark|spots|oju|ri\b|riran|iriran",
    "fever": r"fever|febrile|pyrex|temp|hot\b|heat|chill|rigor|shiver|malaria|typhoid|warm|iba\b"
    r"|igbona|gbona|otutu",
    "severe_abdominal_pain": r"abdom|belly|belle|stomach|tummy|epigastr|cramp|contraction|ikun"
    r"|inu\b|irora",
    "reduced_fetal_movement": r"mov|kick|baby|babies|pikin|fetal|foetal|fetus|foetus|quicken"
    r"|omo\b|mi\b|rin\b|kiri",
    "breathing_difficulty": r"breath|dyspn|wheez|short of|chest|air\b|gasp|pant|suffoc|drown"
    r"|chok|emi\b|mimi|eemi|imu\b",
    "swelling_face_hands": r"swell|swollen|puff|oedem|edem|bloat|face|facial|hand|finger|ring\b"
    r"|wu\b|wiwu|hegehege|egeege|oju",
    "leaking_amniotic_fluid": r"water|fluid|liquor|leak|gush|drain|wet\b|ruptur|membran|rom\b"
    r"|prom\b|discharg|pour|flow|omi\b",
    "severe_vomiting": r"vomit|throw|threw|puke|retch|emesis|food|nause|sick|eebi|ebi\b|bi\b",
    "unconscious": r"conscious|faint|collaps|pass(ed)? out|black(ed)? ?out|respon|wake|woke"
    r"|awake|unrespon|daku|gcs|coma|slump|ji\b|mo nnkan",
    "severe_pallor": r"pale|pallor|pallid|anaemi|anemi|white|blood|funfun|eje\b|conjunctiv|palm"
    r"|haemoglobin|hemoglobin|hb\b|pcv|feefee|fee fee|alawo",
}
CONCEPT_WORDS: dict[str, re.Pattern[str]] = {
    concept: re.compile(rf"\b({words})") for concept, words in _WORDS.items()
}

# A number: digits, English (and Pidgin) number words, or a Yoruba number-word stem.
_NUMBER = re.compile(
    r"\d|\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen"
    r"|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty"
    r"|seventy|eighty|ninety|hundred|point|half)\b"
    r"|(ookan|okan|eeji|meji|eeta|meta|eerin|merin|aarun|marun|eefa|mefa|eeje|meje|eejo|mejo"
    r"|eesan|mesan|eewa|mewa|ogun|ogbon|ogoji|aadota|ogota|aadorin|ogorin|aadorun|ogorun"
    r"|igba|dinl|lel)"
)


@dataclass(frozen=True)
class SupportFlag:
    path: str
    detail: str


def mentions(concept: str, quote: str) -> bool:
    """True if ``quote`` has one of ``concept``'s words, or the concept is not checked."""
    words = CONCEPT_WORDS.get(concept)
    return words is None or bool(words.search(fold_text(quote)))


def has_number(quote: str) -> bool:
    return bool(_NUMBER.search(fold_text(quote)))


def _fmt(value: float) -> str:
    return f"{value:g}"


def check(record: Encounter) -> list[SupportFlag]:
    """Flags for a grounded record (its quotes are the transcript's text)."""
    out: list[SupportFlag] = []
    for i, f in enumerate(record.findings):
        if f.evidence is None or f.assertion in (Assertion.absent, Assertion.not_mentioned):
            continue
        if not mentions(f.concept, f.evidence.text):
            out.append(
                SupportFlag(
                    f"findings[{i}]",
                    f'{f.concept} is "{f.assertion.value}", but its quote does not mention it:'
                    f' "{f.evidence.text}"',
                )
            )
    v = record.vitals
    measured = [
        ("blood_pressure", v.blood_pressure, lambda m: f"{m.systolic}/{m.diastolic} mmHg"),
        (
            "temperature",
            v.temperature,
            lambda m: f"{_fmt(m.value)} °{'C' if m.unit == 'Cel' else 'F'}",
        ),
        ("weight", v.weight, lambda m: f"{_fmt(m.value)} kg"),
        ("pulse", v.pulse, lambda m: f"{m.value}/min"),
    ]
    for name, m, show in measured:
        if m is not None and not has_number(m.evidence.text):
            out.append(
                SupportFlag(
                    f"vitals.{name}",
                    f"{name.replace('_', ' ')} {show(m)} is in the draft, but its quote has no"
                    f' number: "{m.evidence.text}"',
                )
            )
    return out
