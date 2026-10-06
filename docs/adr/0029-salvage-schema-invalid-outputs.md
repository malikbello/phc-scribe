# ADR-0029: Salvage schema-invalid model outputs in serving, instead of rejecting the record

- **Status:** Proposed (needs Malik's decision)
- **Date:** 2026-10-06
- **Changes:** the serving pipeline (`/v1/extract` with the llama.cpp model). The benchmark, its metrics and the frozen-test verdicts are unchanged.

## Context
The decoding grammar enforces the record's JSON schema, but not its cross-field rules. The commonest failure is a lab test named without a result ("urine protein" and nothing else), which the record rule "a test needs a result or a value" rejects. Today the API returns a 502 for such an output, so the health worker gets **no draft at all** for a visit that was otherwise documented correctly.

On the frozen sets this was found post hoc (`docs/results-frozen-tests.md`, G1 sensitivity): 35 of 1,090 shipped-model outputs were invalid, 29 of them for this reason. The frozen results stand as registered, and this ADR does not re-score them.

## Decision
1. **Three repairs, fixed in advance** (`serve/phc_scribe/salvage.py`). Each removes only a part with no clinical content, or one that repeats a kept part:
   - a test with neither a result nor a value;
   - a medication coded `other` with no name;
   - a repeated finding (same concept and assertion; the first is kept).
2. **Nothing is invented or changed.** No value is guessed (for example, a missing unit is **not** filled in), and invalid JSON (cut-off output) is never patched.
3. **Salvage runs only after strict validation fails,** so valid outputs are never touched.
4. **Every repair is reported** in `grounding.dropped` with reason `schema_repair`, and `needs_review` is true. The health worker sees what was removed, as with ungrounded fields. The danger-sign rules then run on the salvaged record as usual.
5. **Validation on non-test data only** (`scripts/salvage_check.py`, which refuses frozen files). Pilot set, 30 items per system (`results/salvage/pilot.20261006.json`):
   - base HF: 1 invalid, salvaged (duplicate finding);
   - base Q4: 1 invalid, salvaged (test without result);
   - the shipped fine-tuned model (run C-fs): 0 invalid, so nothing to salvage;
   - run C at LoRA scale 0.5 (not shipped): its 11 invalid outputs have other, multiple violations, so salvage correctly leaves them invalid; the same holds for its 1 invalid output at scale 0.75;
   - **valid outputs changed: 0** in every file.

   Dev-set predictions live on the Modal volume (`/_eval/`), not in git. Running the same check on them is a laptop step (see Consequences).

## Consequences
- **Fewer failed drafts:** fewer 502s on real visits; the nurse gets a reviewable draft instead of an error.
- **The benchmark is unchanged:** it still scores invalid outputs as registered. The serving effect on the frozen sets is reported **post hoc only**, from the existing "repaired" row of the G1 sensitivity analysis:
  - false alarms 9.5% vs 9.3% registered;
  - 30 of 33 invalid outputs recovered on H.
- **Laptop check before relying on it:** run `scripts/salvage_check.py` on the dev predictions from the Modal volume.
- **Risk:** a removed test could have mattered clinically (for example "urine protein done, result pending"). Mitigation: the removal is shown to the health worker for review, never silent.
