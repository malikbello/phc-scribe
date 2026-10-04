# ruff: noqa: E501  (REJECT/RELABEL keys are exact generated sentences and must stay unbroken)
"""ADR-0027 amendment (4 Oct): curate the English synthetic sentences, then translate-train.

    python -m bench.synth_curate --checked data/private/synth/checked.jsonl \
        --out data/private/synth/en.curated.jsonl

Free generation in Yoruba and Pidgin by base N-ATLaS failed the quality gate: many kept
sentences were nonsense or mixed other languages, and the round trip (N-ATLaS checking itself)
did not catch them. English generations were fluent, but some gold labels were wrong (e.g.
"I haven't noticed the baby moving much" generated for reduced_fetal_movement *absent*, which
actually means present). So:
1. English sentences are curated: every kept English sentence was read; decisions below,
   keyed by the exact text.
2. Yoruba and Pidgin come from translating the curated English with N-ATLaS (greedy), then
   back-translating to English. A translation is kept only if it passes the target-language
   rules and the back-translation passes the English rules and still names the symptom
   (`concept_named`).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Rejected after reading: refusals, a second unlabelled symptom, ambiguous time or meaning,
# off-topic text.
REJECT = {
    "I feel like something is wrong today, my chest is tight.",
    "I'm sorry, but I can't fulfill this request as it violates the content guidelines. Please provide a different prompt.",
    "I'm feeling tired today, but I don't have trouble breathing.",
    "I have epilepsy, and when I have a seizure, my body shakes and I fall.",
    "I feel a little feverish and I have a persistent cough, can you help?",
    "I felt the baby moving less than usual like in my last pregnancy.",
    "In my last pregnancy, I always had a really bad stomach ache and couldn’t keep any food down.",
    "I've been feeling tired all the time, so my doctor told me to get more rest and he recommended this new pillow to support my growing belly.",
    "I've been feeling dizzy and fainted now, I'm worried about my baby.",
    "I've been feeling dizzy and just passed out, Nurse.",
    "I feel like I'm losing consciousness today, nurse.",
}
# Wrong gold fixed after reading: text -> (concept, assertion).
RELABEL = {
    "I don't notice the baby moving as much as I used to.": ("reduced_fetal_movement", "present"),
    "I haven't noticed the baby moving much in recent days.": ("reduced_fetal_movement", "present"),
    "I don't have morning sickness, nurse, because I can eat food every day.": (
        "nausea_vomiting",
        "absent",
    ),
}

# The symptom must still be named in the back-translation (lower-case English).
CONCEPT_WORDS: dict[str, str] = {
    "vaginal_bleeding": r"bleed|blood",
    "convulsions": r"fit|convuls|seizure|shak|jerk",
    "severe_headache": r"head",
    "headache": r"head",
    "blurred_vision": r"blur|see|vision|sight|eye",
    "swelling_face_hands": r"swell|puff",
    "severe_abdominal_pain": r"belly|stomach|abdom|tummy",
    "abdominal_pain": r"belly|stomach|abdom|tummy",
    "fever": r"fever|hot|temperature",
    "reduced_fetal_movement": r"baby|child|foetus|fetus",
    "leaking_amniotic_fluid": r"water|fluid|leak",
    "breathing_difficulty": r"breath",
    "unconscious": r"faint|conscious|pass(ed)? out|collapse",
    "severe_vomiting": r"vomit|throw|food|nause",
    "nausea_vomiting": r"vomit|nause|sick|throw",
    "low_back_pain": r"back|waist",
    "leg_cramps": r"cramp|leg",
    "heartburn": r"chest|burn|heart",
    "constipation": r"constipat|stool|toilet|poo",
    "fatigue": r"tire|weak|fatigue|exhaust",
    "dizziness": r"dizz|spin|turn",
    "cough": r"cough",
    "painful_urination": r"urin|pee|wee",
    "leg_oedema": r"swell|leg|feet|foot",
    "abnormal_vaginal_discharge": r"discharge",
    "pelvic_pain": r"pelvi|lower|waist",
}


def concept_named(concept: str | None, english: str) -> bool:
    return concept is None or bool(re.search(CONCEPT_WORDS[concept], english.lower()))


def curate(rows: list[dict]) -> list[dict]:
    out, seen = [], set()
    for r in rows:
        if not r.get("kept") or r["language"] != "en":
            continue
        text = r["text"]
        if text in REJECT or text in seen:
            continue
        seen.add(text)
        if text in RELABEL:
            r = {**r, "concept": RELABEL[text][0], "assertion": RELABEL[text][1]}
        out.append(
            {k: r[k] for k in ("id", "language", "concept", "assertion", "text")} | {"kept": True}
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checked", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = [
        json.loads(x) for x in args.checked.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    out = curate(rows)
    args.out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8"
    )
    print(f"{len(out)} curated English sentences -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
