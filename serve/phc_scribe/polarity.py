"""Polarity check: a finding whose own quote seems to say the opposite (ADR-0030).

Grounding proves a quote is in the transcript, not that it supports the assertion. The
shipped model once wrote ``reduced_fetal_movement: present`` with the quote "the baby moves
well". This check reads the quote, as a person would, for two cues:

1. **Normal state**, for the concepts that are themselves an absence (reduced fetal
   movement, unconscious): "moves well", "ń mì dáadáa", "alert". If the quote describes the
   normal state and has no negator, a present/possible/historical assertion is suspect.
2. **Denial**, for every other concept: the quote is a denial ("no bleeding", "denies
   headache", "Kò sí ibà", "Any bleeding? No").

Plain negation detection (NegEx) would be wrong here: in Pidgin and Yoruba a symptom is
often said with a negator ("pikin no dey move", "I no fit see well", "ọmọ kò mì dáadáa"),
and those are present findings. So the cues are narrow, and a hit only **flags** the finding
for the health worker; nothing is dropped or changed. Matching runs on folded text (no tone
marks, lower case; phc_scribe.text).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from phc_scribe.encounter import Assertion, Encounter
from phc_scribe.text import fold_text

# Concepts whose presence is an absence of the normal state.
INVERTED = frozenset({"reduced_fetal_movement", "unconscious"})

# Any negator. Used only to *exclude* a normal-state reading ("kò mì dáadáa" is present).
_NEGATOR = re.compile(
    r"\b(no|not|never|cannot|can't|cant|isn't|isnt|doesn't|doesnt|don't|dont|hasn't|hasnt|"
    r"stopped|less|reduced|decreased|hardly|barely|ko|ki i|kii|o ti|rara|kosi)\b|n't\b"
)

_NORMAL: dict[str, re.Pattern[str]] = {
    "reduced_fetal_movement": re.compile(
        r"\b(mov(e|es|ed|ing)|kick(s|ed|ing)?|active)\b.*\b(well|fine|normal(ly)?|ok|okay|good|plenty|"
        r"well well|as (usual|before|normal))\b"
        r"|\b(normal|good|active) (fetal |foetal |baby )?movements?\b"
        r"|\bfetal movements? (felt|present|normal|good|active)\b"
        r"|\bdey (move|kick)\b"
        r"|\bn mi (daadaa|dada|bi o se ye|gan)\b|\bsi n mi\b"
    ),
    "unconscious": re.compile(r"\b(conscious|alert|awake|responsive|oriented|talking well)\b"),
}

# A denial: the quote opens with a negating word, or is an answered question ending "no".
_DENIAL = re.compile(
    r"^(no|nil|denies|denied|deny|without|negative for|not|never|none|"
    r"i no get|she no get|no get|ko si|kosi|ko ni|ko si nkan|rara)\b"
    r"|\b(denies|denied|negative for|no history of|no complaints? of)\b"
    r"|\b(has|have|had|with|reports|got|get) no\b"
    r"|\?\s*(no|nope|rara|no o|no ma|no ma'am)\b"
    r"|\bno (longer|more)\b"
)
# Clinical-note style: "fits: nil", "oedema - none" (annotation guidelines: "nil" = negative).
_TRAILING_NIL = re.compile(r"[:\-]\s*(nil|none|no|negative|absent)\.?$|\bnil\.?$")
# An explicit clinical denial; used for the inverted concepts too ("denies unresponsiveness").
_EXPLICIT = re.compile(r"\b(denies|denied|deny|negative for|no history of)\b")
# A negation's scope ends at a comma, semicolon, full stop or "but" (annotation guidelines).
_CLAUSES = re.compile(r"[,;.]|\bbut\b|\bsugbon\b")
# Verb negations that state a symptom ("no dey see well", "cannot see"): never a denial.
_SYMPTOM_NEGATION = re.compile(r"\b(no (dey|fit|can|able)|not able|cannot|can't|cant|unable)\b")


@dataclass(frozen=True)
class PolarityFlag:
    path: str
    concept: str
    assertion: str
    cue: str  # "normal_state" or "denial"
    quote: str

    @property
    def detail(self) -> str:
        reads = "the normal state" if self.cue == "normal_state" else "a denial"
        return (
            f'{self.concept} is "{self.assertion}", but its quote reads as {reads}: "{self.quote}"'
        )


def reads_opposite(concept: str, assertion: str, quote: str) -> str | None:
    """The cue (``normal_state`` or ``denial``) if ``quote`` seems to contradict the
    assertion, else None. Only non-absent assertions are checked: a false "absent" is a
    miss, which this check cannot judge from the quote alone."""
    if assertion in (Assertion.absent, Assertion.not_mentioned, "absent", "not_mentioned"):
        return None
    q = fold_text(quote).strip()
    # Judged clause by clause: "bleeding per vaginam; denies gush of fluid" is not a denial
    # of bleeding. Every clause must be a denial (or the normal state) to flag.
    clauses = [c.strip() for c in _CLAUSES.split(q) if c and c.strip(" ?!:-")]
    if not clauses:
        return None
    if concept in INVERTED:
        normal = _NORMAL[concept]
        if all(normal.search(c) and not _NEGATOR.search(c) for c in clauses):
            return "normal_state"
        return "denial" if all(_EXPLICIT.search(c) for c in clauses) else None
    if all(_is_denial(c) for c in clauses):
        return "denial"
    return None


def _is_denial(clause: str) -> bool:
    if _SYMPTOM_NEGATION.search(clause):
        return False
    return bool(_DENIAL.search(clause) or _TRAILING_NIL.search(clause))


def check(record: Encounter) -> list[PolarityFlag]:
    """Flags for a grounded record's findings (their quotes are the transcript's text)."""
    out: list[PolarityFlag] = []
    for i, f in enumerate(record.findings):
        if f.evidence is None:
            continue
        cue = reads_opposite(f.concept, str(f.assertion.value), f.evidence.text)
        if cue:
            out.append(
                PolarityFlag(
                    f"findings[{i}]", f.concept, str(f.assertion.value), cue, f.evidence.text
                )
            )
    return out
