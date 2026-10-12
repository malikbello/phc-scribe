# ADR-0036: Flag a value whose own quote does not say it (support check)

- **Status:** Proposed 12 Oct 2026; built and tested. Flag-only, so it is safe to run while it awaits review.
- **Date:** 2026-10-12
- **Changes:** the serving pipeline (`/v1/extract`) adds `{reason: "support"}` entries to `grounding.checks` (ADR-0030's list). Additive; existing clients keep working. The benchmark, its metrics and the frozen-test verdicts are unchanged: nothing is dropped or changed.

## Context
This is the first end-to-end test of the whole system on the laptop hub (12 Oct 2026). The real app ran on a phone-sized screen and played a recorded English visit through the microphone. The hub ran speech recognition, the fine-tuned N-ATLaS and the danger-sign rules. Speech recognition wrote:

> mrs. adebayo 28 wk 2nd pregnancy she has had some bleeding from the vaginal scenes yesterday and a severe headache since this morning the baby moved well no fever the bps 120 over 80 are i think i need to refer her to the general hospital today.

The draft, which took 12.9 minutes on a laptop with under 2 GB of memory free:

| Value | Quote | What happened |
|---|---|---|
| Vaginal bleeding: present | "she has had some bleeding from the vaginal scenes yesterday" | right; the quote shows the speech error "scenes" |
| Severe headache: present | "the baby moved well no fever the bps 120 over 80 …" | right finding, wrong quote (the headache was the sentence before) |
| Reduced fetal movement: present | "the baby moved well" | wrong; **flagged** by the polarity check (ADR-0030) |
| Temperature 37 °C | "no fever" | invented from "no fever"; **not flagged** |
| Blood pressure 120/80 | (the model's quote was not in the transcript) | dropped by grounding; the nurse sees "ungrounded" |

The danger-sign banner ("Refer now") was right on both real signs. Two things got past every check: a quote about something else, and a measurement with no number in its quote. The error taxonomy (`docs/error-taxonomy.md`, section 4.1) had already listed the first as the next check: 48 of 70 false-bleeding findings in G quote unrelated text such as "TCA 4/52". The grounding docstring says why the second passed: numbers said as words (common in Yoruba) cannot be checked against digits, so a quote with no digits passes.

## Decision
1. **Concept words** (`serve/phc_scribe/support.py`). A present, possible or historical **danger-sign** finding is flagged when its quote has none of the concept's words in English, Pidgin or Yoruba. Examples: "bleed", "blood", "spotting", "ẹ̀jẹ̀"; "head", "orí"; "belle", "ikùn". "Looks very ill" is a general impression with no fixed words, so it is not checked.
2. **A number.** A blood pressure, temperature, weight or pulse is flagged when its quote has no number at all. That means no digits, no English number words ("thirty seven point five") and no Yoruba number-word stems ("mẹ́tàdínlógójì").
3. **Flag, never drop or change**, as in ADR-0030. A hit adds `{path, reason: "support", detail}` to `grounding.checks`. Takada already shows every check under "Please check", so the app needs no change. For example: "Check this: temperature 37 °C is in the draft, but its quote has no number: "no fever"".
4. **Wide word lists on purpose.** A miss costs one unflagged error. A false flag costs the nurse's attention on every visit. The lists were written from the training set. Two additions came after the dev check: "unresponsiveness", from a pilot item, and the Yoruba for pale ("aláwọ̀ fẹ́ẹ́fẹ́ẹ́"), from a dev item.
5. **Measured on non-test data only.** `scripts/support_check.py` refuses frozen files (ADR-0022) and writes `results/support/dev.20261012.json`. Private text is counted, never written.
   - **Gold danger findings** with clean labels: 26 pilot items, 28 phrasebank entries, and 91 items written for training (76 train, 15 dev). **0 of 145 flagged.**
   - **Gold findings on real speech items** (labels from a teacher model): 43 of 128 (train) and 13 of 26 (dev) flagged. In these items the quote itself does not say the sign; the label is noise. Examples: "boya" ("maybe") labelled fever, "jejere" ("cancer") labelled bleeding. A nurse reading those quotes would also find no danger sign.
   - **Saved model predictions** (9 runs on the pilot and dev items, 224 danger findings): **54 flagged, 52 of them wrong by gold.** The 2 others are on real speech items, where gold is the noisy teacher label. For the shipped model's pilot run, 7 were flagged and all 7 were wrong.
   - **Measurements:** none of the 178 predicted vitals in those runs was flagged. All their quotes have digits, so there were no false flags, and only the end-to-end case shows the check catching something.

## Limits (said plainly)
- **Developed on the data it is measured on,** like the polarity check. The numbers are an optimistic check, not an estimate. The pilot-day transcripts and later non-test data decide.
- **A quote can mention the concept and still be wrong.** "The baby moved well" mentions the baby: the polarity check catches that one, this check does not. A quote that names the sign in a denial ("no headache") is left to the polarity check too.
- **Word lists miss rare phrasings,** above all Yoruba from speech recognition. A miss means no flag, never a dropped finding.

## Consequences
- **The end-to-end draft now shows four notes under "Please check":**
  - the fetal-movement polarity flag;
  - the headache quote;
  - the invented temperature;
  - the ungrounded blood pressure.

  The real danger signs and the "Refer now" banner are unchanged.
- **Next:** measure both checks again on the pilot-day transcripts. If precision stays this high, a later ADR may let a support flag replace a wrong quote with the closest sentence that names the sign. A finding is never dropped on these checks alone.
