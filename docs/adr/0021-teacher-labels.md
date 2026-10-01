# ADR-0021: Teacher labels from Llama-3.1-8B for real training speech

- **Status:** Accepted by Malik, 1 Oct 2026 (proposal D in `docs/research/finetuning-review.md`)
- **Date:** 2026-10-01
- **Changes:** how part of the training data is labelled (ADR-0016 §4 named human labels plus rule pre-annotation).

## Context
- Human labelling time is scarce and goes to the test set first.
- The literature shows LLM teacher labels can train students that match or beat the teacher on clinical extraction (`docs/research/finetuning-review.md` §2.5).
- On our pilot, Llama-3.1-8B-Instruct few-shot (N-ATLaS's parent) reached danger-sign recall 0.95 with no false alarms and 29/30 valid outputs; base N-ATLaS reached 0.60.
- Real Yoruba and Pidgin examples matter for transfer (§2.4); our generated notes are English only.

## Decision
1. **Source:** unlabelled health speech from **training splits only**: WazobiaSpeech `train` (yo, pcm), and MAMAI `train` if access arrives. Speakers in any test pool are excluded (checked by `scripts/fetch_wazobia.py --check-speakers` and `scripts/build_train_set.py`).
2. **Teacher:** Llama-3.1-8B-Instruct, prompt-v0.1 few-shot, greedy, constrained decoding, on Kaggle.
3. **Filter, written down before use:** keep an output only if it is schema-valid, every evidence quote is found verbatim in the transcript (our grounding check), and it has no assertion the rules engine rejects. Items with no finding are kept (they teach the model when to stay quiet), capped at half of the teacher-labelled set.
4. **Check:** Malik (or Oseni) reviews a random 50 kept items in the review app; the agreement rate is reported. If more than 1 in 5 kept items is wrong on a danger sign, the teacher labels are not used.
5. **Disclosure:** the model card states which training items are teacher-labelled.
6. **Licence:** the Llama 3.1 Community License allows training on its outputs, but a model trained on them and distributed must include "Llama" at the start of its name. Malik checks the N-ATLaS terms (also Llama-based) and names the released adapter accordingly before release.

## Consequences
- Real Yoruba/Pidgin training data without spending the team's labelling time.
- Risk: the student inherits the teacher's errors. The filter, the 50-item check and the frozen test set (labelled by humans only) contain it.
- Teacher labels never touch the test set.
