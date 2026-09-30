# Base-model baselines, 30 Sept 2026

Score reports from the Kaggle job `bellomalik/phc-scribe-baseline` (T4, started 08:04 UTC,
finished between 16:01 and 16:11 UTC), copied verbatim from the job log (the prediction files stay in the
notebook's Output tab; `kaggleusercontent.com` is not reachable from the cloud session).

- Prompt: `prompt-v0.1` (`bench/prompts.py`); greedy decoding, JSON-schema-constrained
  (xgrammar), `max_new_tokens = 768`.
- Systems: N-ATLaS few-shot, Llama-3.1-8B-Instruct few-shot (`unsloth/Llama-3.1-8B-Instruct`),
  N-ATLaS zero-shot.
- Sets: `data/bench/g.20261002.jsonl` (G: 300 generated notes, all English) and
  `tests/fixtures/smoke_items.jsonl` (6 constructed items; 2 are the few-shot examples, so the
  few-shot smoke scores are a pipeline check only).
- CIs: 95% bootstrap, resampled by group (`bench/stats.py`).
