"""In-language synthetic training statements written by base N-ATLaS (ADR-0028).

    python -m bench.synth spec --out data/private/synth/prompts.jsonl
    # on Modal: deploy/modal_train.py::synth (generate, rule-check, round-trip check)
    python -m bench.synth compose --sentences data/private/synth/checked.jsonl \
        --out data/private/synth/synth.v1.jsonl

Why: the real training data has 126 danger-sign examples, 74 of them bleeding, and none
for reduced fetal movement or loss of consciousness. The test (S5, G) covers every sign.

What: for every language (yo, pcm, en), symptom and assertion (present, denied, unsure,
past pregnancy), base N-ATLaS writes short first-person sentences by a pregnant woman.
- **Rule checks:** language markers; the assertion's cue (negation, hedge, past pregnancy);
  severity words only for severe concepts; length.
- **Round trip:** N-ATLaS classifies each sentence again from scratch (greedy, a different
  prompt); a sentence is kept only if the class matches what was asked for.
Kept sentences are composed into items of 1-3 sentences (each sentence used once), with
general-advice sentences as "nothing to record". The gold is the specification, and the
evidence is the sentence itself.

Independence: S5 (test) was written by the assistant from its own lexicon; these sentences
are written by N-ATLaS. `build_train_set.py` still drops anything that duplicates or nearly
duplicates a frozen test item.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path

from bench.items import BenchItem, write_jsonl
from phc_scribe.encounter import Encounter
from phc_scribe.vocab import load_vocabulary

SEED = 20261013
LANGS = {"yo": "Yoruba (with correct tone marks)", "pcm": "Nigerian Pidgin", "en": "English"}

# Plain-language descriptions (what the woman experiences), not clinical terms.
CONCEPTS: dict[str, str] = {
    "vaginal_bleeding": "bleeding from her private part (vagina)",
    "convulsions": "a fit or convulsion (her body shook and she fell)",
    "severe_headache": "a very bad headache that will not go away",
    "headache": "a slight, mild headache",
    "blurred_vision": "blurred vision (things look unclear)",
    "swelling_face_hands": "swelling of her face and hands",
    "severe_abdominal_pain": "very bad pain in her belly",
    "abdominal_pain": "slight, mild pain in her belly",
    "fever": "fever (her body feels hot)",
    "reduced_fetal_movement": "the baby in her womb moving less than before",
    "leaking_amniotic_fluid": "water leaking from her private part",
    "breathing_difficulty": "difficulty breathing",
    "unconscious": "fainting (losing consciousness)",
    "severe_vomiting": "vomiting so much that no food stays down",
    "nausea_vomiting": "slight nausea or vomiting once",
    "low_back_pain": "pain in her lower back (waist)",
    "leg_cramps": "cramps in her legs at night",
    "heartburn": "a burning feeling in her chest after eating",
    "constipation": "constipation",
    "fatigue": "feeling tired",
    "dizziness": "dizziness",
    "cough": "a cough",
    "painful_urination": "pain when passing urine",
    "leg_oedema": "swollen legs or feet",
    "abnormal_vaginal_discharge": "unusual discharge from her private part",
    "pelvic_pain": "pain low in her pelvis",
}
ASSERTIONS: dict[str, str] = {
    "present": "says she has it now",
    "absent": "clearly says she does NOT have it",
    "possible": "says she is not sure whether she has it",
    "historical": "says she had it in a previous pregnancy (say nothing about now)",
}
# Sentences per (language, concept, assertion).
DANGER_PLAN = {"present": 6, "possible": 3, "absent": 3, "historical": 2}
OTHER_PLAN = {"present": 3, "absent": 1}
GENERAL_PER_LANG = 30
SEVERE = {"severe_headache", "severe_abdominal_pain", "severe_vomiting"}
MILD = {"headache", "abdominal_pain", "nausea_vomiting"}

CUES = {
    "absent": {
        "yo": r"\b(ko|ko si|mi o|rara|kankan)\b",
        "pcm": r"\b(no|never|not|nothing)\b",
        "en": r"\b(no|not|never|don't|haven't|hasn't|didn't|nothing)\b",
    },
    "possible": {
        "yo": r"\b(boya|mo ro pe|o da bi|mi o mo|ko da mi loju)\b",
        "pcm": r"\b(maybe|i think|e be like|i no sure|i no too sure|i no know)\b",
        "en": r"\b(maybe|might|i think|not sure|i'm not sure|perhaps|unsure)\b",
    },
    "historical": {
        "yo": r"\b(oyun akoko|oyun to koja|oyun tele|tele|ateyinwa)\b",
        "pcm": r"\b(first belle|last belle|before|other belle|last pregnancy|first pregnancy)\b",
        "en": r"\b(last pregnancy|previous pregnancy|first pregnancy|before|other pregnancy)\b",
    },
}
SEVERITY_CUE = r"(gidigidi|gan|gan-an|die|serious|very|severe|anyhow|too much|well well|bad)"
PIDGIN_MARKERS = r"\b(dey|na|don|wey|abeg|wetin|pikin|belle|una|dem|fit|sef|no be)\b"
YORUBA_MARKERS = r"[ẹọṣẸỌṢ]|[̀́̄]"


def _plain(text: str) -> str:
    """Lower case without tone marks or under-dots, so Yoruba cues match as plain words."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


PARTNER = {
    "severe_headache": "headache",
    "severe_abdominal_pain": "abdominal_pain",
    "severe_vomiting": "nausea_vomiting",
}
PARTNER |= {v: k for k, v in PARTNER.items()}


def spec(seed: int = SEED) -> list[dict]:
    """One prompt row per sentence to generate."""
    danger = load_vocabulary().danger_sign_ids
    rows = []
    for lang in LANGS:
        for concept in CONCEPTS:
            plan = DANGER_PLAN if concept in danger else OTHER_PLAN
            for assertion, k in plan.items():
                for v in range(k):
                    rows.append(
                        {
                            "id": f"syn-{lang}-{concept}-{assertion}-{v}",
                            "language": lang,
                            "concept": concept,
                            "assertion": assertion,
                        }
                    )
        for v in range(GENERAL_PER_LANG):
            rows.append(
                {
                    "id": f"syn-{lang}-general-{v}",
                    "language": lang,
                    "concept": None,
                    "assertion": None,
                }
            )
    random.Random(seed).shuffle(rows)  # noqa: S311 (data construction)
    return rows


def generation_messages(row: dict) -> list[dict[str, str]]:
    lang = LANGS[row["language"]]
    if row["concept"] is None:
        task = (
            f"Write ONE short sentence in {lang} giving general health advice to pregnant women "
            "(for example about food, rest or clinic visits). It must not describe anyone's own "
            "symptoms. Reply with the sentence only."
        )
    else:
        task = (
            f"Write ONE short sentence in {lang}, spoken in the first person by a pregnant woman "
            f"to a nurse at an antenatal visit. In it she {ASSERTIONS[row['assertion']]}: "
            f"{CONCEPTS[row['concept']]}. Use everyday words, not medical terms. Reply with the "
            "sentence only."
        )
    return [
        {
            "role": "system",
            "content": "You write realistic sentences for a health-worker training dataset.",
        },
        {"role": "user", "content": task},
    ]


def classification_messages(row: dict, text: str) -> list[dict[str, str]]:
    """Round-trip check: what does the sentence say about this symptom?"""
    concept = CONCEPTS[row["concept"]] if row["concept"] else "any symptom of her own"
    return [
        {
            "role": "user",
            "content": (
                f'Sentence: "{text}"\n\nThe speaker is a pregnant woman. About {concept}, '
                "what does she say? Answer with exactly one word:\n"
                "present (she has it now), absent (she says she does not have it), possible "
                "(she is unsure), historical (she had it in a previous pregnancy), none (she "
                "does not talk about her own symptoms)."
            ),
        }
    ]


def clean(text: str) -> str:
    text = text.strip().strip('"“”').strip()
    return re.sub(r"\s+", " ", text.splitlines()[0] if text else "")


def rule_check(row: dict, text: str) -> str | None:
    """None if the sentence passes; otherwise the reason it fails."""
    if not 3 <= len(text.split()) <= 35:
        return "length"
    lang, assertion, concept = row["language"], row["assertion"], row["concept"]
    low = _plain(text)
    if lang == "yo" and not re.search(YORUBA_MARKERS, text):
        return "not_yoruba"
    if lang == "pcm" and not re.search(PIDGIN_MARKERS, low):
        return "not_pidgin"
    if lang == "en" and re.search(PIDGIN_MARKERS, low) and re.search(r"\b(dey|wetin|abeg)\b", low):
        return "not_english"
    if concept is None:
        return None
    if assertion in CUES and not re.search(CUES[assertion][lang], low):
        return f"no_{assertion}_cue"
    if assertion == "present":
        for other in ("absent", "possible"):
            if re.search(CUES[other][lang], low):
                return f"present_has_{other}_cue"
    if concept in SEVERE and not re.search(SEVERITY_CUE, low):
        return "no_severity_cue"
    if concept in MILD and re.search(SEVERITY_CUE, low):
        return "mild_has_severity_cue"
    return None


def parse_class(output: str) -> str:
    words = re.findall(r"[a-z]+", output.lower())
    for w in words[:3]:
        if w in ("present", "absent", "possible", "historical", "none"):
            return w
    return "unparsed"


def compose(rows: list[dict], seed: int = SEED) -> list[BenchItem]:
    """Items of 1-3 checked sentences per language; every sentence is used once."""
    rng = random.Random(seed)  # noqa: S311
    items: list[BenchItem] = []
    for lang in LANGS:
        pool = [r for r in rows if r["language"] == lang]
        rng.shuffle(pool)
        n = 0
        while pool:
            k = min(len(pool), rng.choice([1, 1, 2, 2, 3]))
            chosen, pool = pool[:k], pool[k:]
            # One assertion per concept, and never a severe/mild pair, within an item.
            seen: set[str] = set()
            keep, put_back = [], []
            for r in chosen:
                c = r["concept"]
                family = {c, PARTNER[c]} if c in PARTNER else {c}
                if c is not None and family & seen:
                    put_back.append(r)
                    continue
                if c is not None:
                    seen |= family
                keep.append(r)
            pool += put_back
            if not keep:
                break
            transcript = " ".join(r["text"] for r in keep)
            gold = Encounter.model_validate(
                {
                    "findings": [
                        {
                            "concept": r["concept"],
                            "assertion": r["assertion"],
                            "evidence": {"text": r["text"]},
                        }
                        for r in keep
                        if r["concept"] is not None
                    ]
                }
            )
            items.append(
                BenchItem(
                    item_id=f"syn-{lang}-{n:04d}",
                    group_id=f"syn:{lang}-{n:04d}",
                    stratum="T",
                    language=lang,  # pyright: ignore[reportArgumentType]
                    origin="generated",
                    transcript=transcript,
                    gold=gold,
                )
            )
            n += 1
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("spec")
    s.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("compose")
    c.add_argument("--sentences", type=Path, required=True, help="checked sentences (jsonl)")
    c.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.cmd == "spec":
        rows = spec()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        langs = dict(Counter(r["language"] for r in rows))
        print(f"{len(rows)} prompts -> {args.out}; by language {langs}")
        return 0
    rows = [
        json.loads(x) for x in args.sentences.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    rows = [r for r in rows if r.get("kept")]
    items = compose(rows)
    write_jsonl(args.out, items)
    danger = load_vocabulary().danger_sign_ids
    pos = Counter(
        str(f.concept)
        for i in items
        for f in i.gold.findings
        if str(f.concept) in danger and str(f.assertion) in ("present", "possible")
    )
    print(f"{len(items)} synthetic items from {len(rows)} sentences -> {args.out}")
    print(f"danger-sign positives by concept: {dict(sorted(pos.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
