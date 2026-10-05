# ADR-0028: In-language synthetic training statements written by base N-ATLaS

- **Status:** Accepted by Malik, 4 Oct 2026 ("do the fix and the models").
- **Date:** 2026-10-04
- **Changes:** adds a synthetic part to the ADR-0024 training set. The rare-sign phrase bank (ADR-0024 §3) is set aside while S5 is a test set.

## Context
The pre-freeze dry run of `build_train_set.py` gave 588 training examples:
- **Few danger signs:** only 126 have a danger sign, and **74 of those are vaginal bleeding**.
- **Rare signs missing:** convulsions has 1 example, severe abdominal pain 2, severe headache 4, and **reduced fetal movement and loss of consciousness have none**.
- **Mostly empty:** 53% of examples have nothing to record.

The P1 test sets cover every patient-reportable danger sign evenly: S5 (Yoruba, Pidgin) has 4–9 items per sign, and G (English) also covers all of them. A model fine-tuned on this mix would learn that rare signs do not exist and that "nothing" is usually right. It could then do worse than the base model on exactly what P1 measures.

The draft phrase bank was meant to fill this gap. But it was written by the same author (the assistant), in the same style, as S5, so using it would blur the line between training and test. It also needed two human approvals there is no time for.

## Decision
1. **Generator: base N-ATLaS** (pinned revision `e294476…`).
   - For each language (Yoruba, Pidgin, English), symptom and assertion (present, denied, unsure, past pregnancy), it writes short first-person sentences by a pregnant woman.
   - Counts: danger signs 6 / 3 / 3 / 2 per assertion; other symptoms 3 present + 1 denied; 30 general-advice sentences per language.
   - Prompts use plain descriptions ("the baby moving less than before"), not the test's wording.
2. **Rule checks (`bench/synth.py`):**
   - language markers;
   - the assertion's cue (negation, hedge, past pregnancy), with Yoruba matched without tone marks;
   - severity words only for severe concepts;
   - length 3–35 words.
3. **Round-trip check:** N-ATLaS classifies every rule-passing sentence again from scratch (greedy, a different prompt). It is kept only if the class matches what was asked for. Failures get one more generation.
4. **Composition:**
   - items of 1–3 kept sentences, each sentence used once;
   - one assertion per concept, and never a severe/mild pair, in an item;
   - general advice = nothing to record;
   - gold by construction, with the sentence as evidence.
5. **Training mix:**
   - the synthetic items join the teacher items and their ASR views in `build_train_set.py`;
   - its near-duplicate filter against the frozen test set applies to them too;
   - they are split into train and dev with everything else, so dev also measures danger signs.

## Why this is sound
- **Independent of the test sets:** S5 and R were written by the assistant from fixed lexicons, and G by the note generator from its phrase list. The training sentences are written by N-ATLaS from plain descriptions. Exact and near duplicates of any frozen test item are dropped.
- **An established technique:** generating in-language training data with the base model, then filtering it, is self-instruct-style data generation. The round trip removes sentences whose meaning drifted.
- **No change to the comparison:** both the base and the fine-tuned model are tested on the same frozen sets. The synthetic data changes only what the fine-tuned model learned from.

## Consequences
- Every patient-reportable danger sign gets training examples in every language.
- The training set becomes about half synthetic. This is disclosed in the model card and the report, with the real-only counts beside it.
- **Cost:** about 15 minutes on a Modal A10G.
- **Risk:** N-ATLaS's own phrasing biases the training data toward how N-ATLaS writes. The real teacher data and its ASR views (more than 700 items) keep real speech in the mix.

## Amendment, 4 Oct 2026: quality gate results and the translate-train change
**Free generation failed the quality gate in Yoruba and Pidgin.**
- **The run:** 762 prompts, two attempts each; 369 passed the rule checks and the round trip.
- **Reading the kept sentences:**
  - many Yoruba sentences were nonsense (a "convulsions" sentence about postal delivery);
  - many "Pidgin" sentences mixed in Igbo, Yoruba or Gbe.
- **The round trip did not catch these:** N-ATLaS judging its own output is not an independent check.

**English generations were fluent, but some gold was wrong.** For example, "I haven't noticed the baby moving much" was generated for reduced fetal movement *absent*, but it means *present*.

**What we did instead:**
1. **English, curated:** every kept English sentence was read. 11 were rejected (a refusal, a second unlabelled symptom, ambiguous time) and 3 relabelled. Each decision is keyed by the exact text in `bench/synth_curate.py`, leaving **152 sentences**.
2. **Yoruba, translate-train:** N-ATLaS translated the curated English (greedy) and back-translated to English. A translation is kept only if:
   - the Yoruba passes the rules;
   - the back-translation passes the English rules;
   - the back-translation still names the symptom.

   That left **45 sentences**. A sample read sound.
3. **Pidgin: none.** The translations still mixed in Yoruba and Igbo words, even after filtering for Igbo/Yoruba letters. Pidgin is English-lexified, so the fine-tuned model learns rare signs from the English synthetic items plus the real Pidgin speech in the teacher data.

**Result:**
- 118 synthetic items from 197 sentences, with every patient-reportable danger sign represented (e.g. reduced fetal movement 11, convulsions 8, unconscious 4).
- **Training set `sft.v1`:** 685 training and 127 dev examples. 31 were dropped for overlapping the frozen test set.
- Reported in the model card: the synthetic share, and the absence of synthetic Pidgin.
