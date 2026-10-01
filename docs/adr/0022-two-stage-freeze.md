# ADR-0022: Freeze the test set in two stages: items first, labels before scoring

- **Status:** Accepted by Malik, 1 Oct 2026
- **Date:** 2026-10-01
- **Changes:** the "Freezing" rule in `docs/eval-plan.md` §3 ("the test set is hashed and frozen before any training data is generated"), which hashed whole test files, gold labels included.

## Context
- **The single freeze blocks training on labelling.** `scripts/build_train_set.py` refuses to run until the test files are hashed, and the hash covered the gold labels. The counted set (S4-W, or MAMAI) is labelled by people over several days, so training could not start until the last label was adjudicated. With the deadline on 12 Oct, that leaves too little time to train, evaluate and report.
- **What the freeze protects** is two separate things:
  1. **Train/test separation.** No test item, speaker or near-duplicate text enters training. This depends only on *which items* are in the test set, not on their labels.
  2. **No label tuning.** Gold labels can't be changed after seeing how the fine-tuned model does on them. This only needs the labels fixed *before any fine-tuned model is scored*.
- Mature benchmark practice separates the two: the item list (and its split) is fixed early, and labels are locked before evaluation, with the adjudication process and its exclusions recorded.

## Decision
1. **Stage 1, items.** Before any training data is built, `scripts/freeze_test_set.py items <files>` writes `data/bench/test-manifest.json` with, per test file, the item count and an order-independent SHA-256 of each item's **id, group (speaker), language and transcript**. Gold labels and hints are not hashed. Label queues (no gold yet) can be frozen this way. `scripts/build_train_set.py` runs against a stage-1 manifest. It refuses if any test item changed, and drops training items that share a group with, duplicate or nearly duplicate a test item.
2. **Between the stages**, labelling and adjudication continue (annotation guidelines §7 and §10). Test items stay off-limits for prompts and few-shot examples as before. **No fine-tuned model is run on any counted test item before stage 2.** Base-model runs can happen at any time, because they don't touch the training choices.
3. **Stage 2, labels.** Before any fine-tuned model is scored on the test set, `scripts/freeze_test_set.py labels --labelled <queue>=<gold file>` does the following:
   - It replaces each label queue with its adjudicated, gold-labelled benchmark file.
   - It checks that the file holds exactly the stage-1 items.
   - It hashes the whole file.
   - It records the time.

   The stage-1 hashes stay in the manifest unchanged. Items adjudicated unlabellable (garbled, cut off, wrong language; guidelines §10.6) may be left out **only** if declared with `--exclude`; they are recorded in the manifest and reported (count and reasons). Scoring reads gold only through `load_gold_items`, which refuses a stage-1 manifest or any changed file.
4. **Each stage is one commit**, and the eval plan records the commit hashes. Neither stage is ever redone. A problem found later is reported as a dated note, not fixed in place.
5. **Thresholds** (G1, G2, decoding cap) are already fixed in `docs/eval-plan.md` §6 and stay fixed.

## Consequences
- Training can start as soon as the counted item set is known (5 Oct, the ADR-0016/0018 decision date), while labelling finishes in parallel.
- **Order of work:**
  1. Stage 1, on 5 Oct after the MAMAI decision.
  2. Build the training set, then train.
  3. Finish labelling and adjudicate.
  4. Stage 2.
  5. Score the fine-tuned model.
- **Risk:** a labeller could see fine-tuned outputs before stage 2. Mitigated by rule 2: no fine-tuned run on counted items before stage 2. Training-time checks use the dev set only.
- **Implementation:** `bench/freeze.py` (`freeze_items`, `freeze_labels`, `load_frozen_items`, `load_gold_items`), `scripts/freeze_test_set.py`, tests in `tests/test_freeze_and_sft.py`.
