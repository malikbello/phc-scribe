# Annotation guidelines v0 (antenatal encounter records)

**Status:** DRAFT v0, 29 Sept 2026. For review by the clinical adviser. The open questions in section 9 need her answers before the 60-item agreement round.

These rules turn a visit transcript (or note) into the gold record defined by `schema/encounter.v0.1.json`, using the finding vocabulary in `schema/vocab/anc_concepts.v0.1.yaml`. The same rules apply to the model's output, so a disagreement between annotator and model is a model error, not a style difference.

## 1. Principles
1. **Record what was said, not what you infer.** If the text says "BP is high" but gives no numbers, there is no BP value. Do not diagnose ("pre-eclampsia") and do not fill gaps from clinical knowledge.
2. **Every value needs evidence:** a verbatim quote from the transcript. Copy it exactly (same spelling, same tone marks) and keep it short: the smallest contiguous piece of text that supports the value.
3. **When unsure between two readings, choose the one a cautious clinician would act on.** Use `possible` rather than leaving a danger sign out. False alarms are preferred to misses.
4. **Only the pregnant woman's own findings are recorded.** Symptoms of her husband, child, sister or another patient are left out.

## 2. Findings and assertion status
List only findings that are mentioned. Each has a `concept`, an `assertion` and `evidence`.

| Assertion | Use when | Examples |
|---|---|---|
| `present` | Stated as happening in this pregnancy, now or since the last visit | "complains of headache"; "ẹ̀jẹ̀ ń jáde" |
| `absent` | Explicitly denied or negated | "no bleeding"; "denies convulsions"; "Any bleeding? No."; "Kò sí ibà" |
| `possible` | Hedged, uncertain, or suspected | "maybe fever at night"; "she's not sure the baby moved"; "?PROM"; "bóyá" |
| `historical` | In a previous pregnancy or in the past, not current | "bled in her last pregnancy"; "history of fits as a child" |
| `not_mentioned` | Do not annotate. A concept that is not listed is implicitly not mentioned | |

Rules:
- **Question and answer:** when the nurse asks and the woman answers, the evidence spans both if they are contiguous ("Any bleeding? No."). A question with no answer is not annotated.
- **Negation scope:** a negation applies until the next comma, "but"/"ṣùgbọ́n", or sentence end, unless the list is clearly all negated ("no bleeding, headache or fever" negates all three; annotate each as `absent` with the whole phrase as evidence).
- **Both past and present:** "bled in the last pregnancy, no bleeding now" gets two findings: `historical` and `absent`.
- **Severity pairs:** choose the severe concept only when the text says severe, very bad, serious, persistent, "gidigidi", "gan", or equivalent. Otherwise use the mild concept:
  - `severe_headache` / `headache`
  - `severe_abdominal_pain` / `abdominal_pain`
  - `severe_vomiting` / `nausea_vomiting`
- **Swelling:** face or hands (or "whole body") is `swelling_face_hands`; feet, ankles or legs only is `leg_oedema`.
- **Examination findings** said by the health worker count as findings ("she is very pale" gives `severe_pallor`; "looks very ill" gives `looks_very_ill`).
- **Evidence for negated or hedged findings includes the cue** ("no bleeding", not just "bleeding").

## 3. Vitals
Record a vital only when a number is stated.
- **Blood pressure:** systolic and diastolic, unit `mm[Hg]`. "140 over 90", "140/90" and "BP 14/9" (shorthand for 140/90) are all 140/90. If only one number is given, do not record BP; note it in the adjudication log.
- **Temperature:** the value and unit as said (`Cel` or `[degF]`). Don't convert.
- **Weight** in kg; **pulse** in beats per minute.
- If several readings are given (e.g. a repeat BP), record the **last** one and quote it.

## 4. Pregnancy and ANC fields
- **Gestational age:** weeks (and days if said). Note shorthand: "32/40" = 32 weeks. "EGA 28 weeks 3 days" = 28 weeks, 3 days. Do not compute GA from LMP or EDD.
- **Gravida / parity:** "G3P2" = gravida 3, parity 2. "P2+1" = parity 2 (the +1 is miscarriages/abortions, not recorded in v0.1). "Primigravida" = gravida 1, parity 0.
- **Contact number:** only if stated ("second ANC visit", "booking visit" = 1).
- **Tests:** record the result as said.
  - Hb in g/dL; PCV in %.
  - Urine protein and glucose as negative / trace / 1+ to 4+ ("++" = 2+; "nil" = negative).
  - Malaria RDT, HIV, syphilis and hepatitis B as positive / negative ("non-reactive" = negative).
  - A test that was ordered but has no result is not recorded.
- **Medications given or prescribed at this visit:**
  - `iron_folic_acid` (ferrous sulphate, fefol, haematinics)
  - `ipt_sp` (SP, Fansidar)
  - `tetanus_diphtheria` (TT, Td)
  - `deworming` (mebendazole, albendazole)
  - `calcium`
  - `other`, with the name as said

  Medications she "is taking" from before are not recorded in v0.1.

## 5. Disposition
- **Referral:** `referred: true` with the destination if named ("Referred to Adeoyo" → destination "Adeoyo"). An explicit "not referred" / "no referral needed" is `referred: false`. Otherwise leave it empty.
- **Next visit:** the text as said ("TCA 2/52", "in four weeks", "on 12 October"). Fill `date` only when a full calendar date is said.
- **Referral summary:** not annotated in the gold set (free text, not scored in v0).

## 6. Yoruba and code-switching
- Quote Yoruba evidence exactly as written in the transcript, tone marks included. The grounding step also matches without tone marks, but gold quotes stay exact.
- Mixed-language sentences are normal ("BP rẹ̀ jẹ́ 150/100"). Annotate as usual.
- Numbers said in words ("ọgọ́jọ") are recorded as their numeric value, with the words as evidence. Malik checks every Yoruba number.

## 7. Process
1. Malik and the medical student each label the same 60-item overlap set independently.
2. Agreement is computed per field (Cohen's κ for assertion; exact match for numbers). Target κ ≥ 0.7. Below that, these guidelines are revised and the round repeated.
3. Every disagreement goes to the clinical adviser, whose decision is final and logged (item, field, both labels, decision, reason).
4. After the overlap round, items are split between annotators. A random 10% of each person's items are spot-checked.
5. **Test items are never used for prompt design, few-shot examples or tuning.**

## 8. Worked example (constructed)
> "Second ANC visit. G2P1, GA 28/40. BP 160/110. She complains of severe headache and blurred vision since morning. No vaginal bleeding. Her sister had convulsions. Referred to the General Hospital."

- findings:
  - `severe_headache` present ("severe headache")
  - `blurred_vision` present ("blurred vision")
  - `vaginal_bleeding` absent ("No vaginal bleeding")
  - (no convulsions: they were the sister's)
- vitals: BP 160/110 ("BP 160/110")
- anc: GA 28 weeks ("GA 28/40"); gravida 2 and parity 1 ("G2P1"); contact 2 ("Second ANC visit")
- disposition: referred, destination "General Hospital" ("Referred to the General Hospital")

## 9. Open questions for the clinical adviser
1. Is the danger-sign list in the vocabulary complete for Nigerian PHC practice? Add, merge or drop any?
2. Should "headache" with BP ≥ 140/90 be treated as a danger sign even when it is not described as severe?
3. Is "BP 14/9" shorthand common enough to rely on, or should it go to review?
4. Should a single BP number ("systolic 150") be recorded?
5. Is PCV < 21% an acceptable stand-in for Hb < 7 g/dL in the severe-anaemia rule?
6. Which edition and sections of the National Standing Orders should each rule cite?
7. Are there common local terms (English or Yoruba) for these signs that we are missing?

## 10. Real speech sets (S4-W, WazobiaSpeech)
_Added 1 Oct 2026 (ADR-0018). Applies to every item whose source is `wazobia`. The app shows a "Real speech" banner on these items and offers only the skip reasons below._

The clips are everyday health talk from Yoruba and Pidgin speakers: some describe their own symptoms, most give general advice or opinions. **Both kinds are wanted.** Items with nothing to record are the negatives that measure false alarms (ADR-0018 §3), so they must be labelled, not skipped.

1. **Who is the patient.** Treat the speaker as the patient. Record findings about:
   - the speaker ("I", "mi", "my belle dey pain me"); or
   - one specific pregnant woman the speaker is reporting on ("my wife dey bleed since morning").

   Do **not** record findings about babies or children, other named people who are not pregnant, or "people", "women" or "pregnant women" in general.
2. **General talk is "Nothing to record".** Advice ("if you get fever, go hospital"), facts ("pregnant women fit get high BP"), opinions, questions without an answer, and hypotheticals ("if your leg swell…") get **Nothing to record**. This is the commonest correct answer.
3. **Present, absent, possible and past apply as in §2.** "I no dey bleed again" is `absent`; "I bled when I carried my first child" is `historical`.
4. **The finding must be one in the vocabulary.** A real complaint outside it (e.g. toothache, "body pain") is Nothing to record; write a note if you think the vocabulary is missing something common.
5. **Ignore transcription marks** such as `[um]`, `[cough]` or `[noise]`. Don't include them in evidence unless they sit inside the phrase.
6. **Skip only when the item cannot be labelled:**
   - **Can't understand it**: garbled, cut off mid-thought so the meaning is lost, or not Yoruba, Pidgin or English;
   - **Duplicate**;
   - **Other** (with a note).

   Never skip because a clip is "not about pregnancy" or "not her own symptoms": those are Nothing to record.
7. **Hints are off** for this set. Label from the words alone.
8. **Process** (ADR-0018 §4, as run):
   - **Calibration first:** every labeller labels the same 20 calibration clips (practice set, drawn from the pool but not from the counted queue). Malik reviews the disagreements with Rahmat; this section is revised if a rule caused them. The calibration clips are never counted.
   - **Then the counted queue** (600 clips): 20% are labelled independently by two people (blind; nobody sees another's label).
   - **Agreement** is reported per item (exact match of finding, assertion and the nothing-to-record decision), with Cohen's κ on danger-sign positivity (present or possible, per pair and danger sign) and pairwise F1; the admin page shows all three.
   - **Adjudication:** Rahmat decides every overlap disagreement that involves a danger sign; Malik decides the rest. Decisions are logged (item, both labels, decision, reason) and the adjudicated label is the gold.
   - Labels are frozen at stage 2 of the freeze (ADR-0022), before any fine-tuned model is scored on them.
