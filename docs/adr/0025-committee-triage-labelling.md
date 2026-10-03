# ADR-0025: Committee pre-labelling, risk-based human review and stratified PPI for the benchmark

- **Status:** Proposed, 3 Oct 2026. Needs Malik's approval (and Rahmat's view) before use.
- **Date:** 2026-10-03
- **Changes:** how the counted benchmark's gold labels are produced (ADR-0016 §4, ADR-0018, eval plan §4). The stage-1 freeze (items, ADR-0022) is unaffected; the stage-2 freeze (labels) applies to the result.

## Context
- The counted benchmark needs 720 human labels (600 clips, 20% double-labelled) by about 8 Oct.
- At 3 Oct, 0 are done; the clinical team's time is the binding constraint.
- Labelling every clip by hand is how small teams start. Mature teams spend human effort where it changes the answer, and use statistics to keep the estimate honest.
- Three findings from the literature shape what is safe:
  1. **Showing model pre-labels anchors annotators.** They defer to the suggestion, and accuracy falls when the model is wrong ([Bias in the Loop, 2025](https://arxiv.org/html/2509.08514v1); ACL Findings 2025). Our labellers stay blind (hints off), as now.
  2. **Disagreement among several independent LLMs finds the hard items.** In clinical extraction from free-text reports, with four local models:
     - the lowest-agreement 6.5% of items held about **80% of the errors**;
     - items where 3–4 models agreed had a **0%** error rate;
     - AUC 0.991 for the disagreement score ([medRxiv 2026](https://www.medrxiv.org/content/10.64898/2026.05.04.26352392v1.full)).
  3. **Prediction-powered inference (PPI)** combines a large automatically labelled set with a small random human-labelled sample to give **unbiased estimates with valid confidence intervals**, with no assumption that the automatic labels are right. The stratified version tightens the intervals further ([Angelopoulos et al., Science 2023](https://www.science.org/doi/10.1126/science.adi6000); [Stratified PPI, NeurIPS 2024](https://arxiv.org/abs/2406.04291)).
- **Circularity risk:** our training labels come from Llama-3.1-8B (ADR-0021). If the same model family labelled the test set, a student trained on its labels would look better than it is. The committee must exclude it, and N-ATLaS (the system under test).

## Decision
1. **Committee.** Three open models from different families, none of them Llama-3.1 or N-ATLaS:
   - Qwen3-14B-Instruct;
   - Gemma-3-12B-it;
   - Mistral-Small-3.x-24B-Instruct.

   Each labels all 600 clips on Kaggle (free; the data never leaves our accounts), with the same prompt (prompt-v0.1 few-shot), constrained decoding and grounding check as every other system.
2. **Two strata, fixed before the committee runs:**
   - **A, human review:** any member reports a danger sign (present or possible), or the members disagree on the set of findings, or any member's output is invalid or ungrounded.
   - **B, committee consensus:** all three agree exactly, with no danger sign.
3. **Humans label:**
   - **every stratum-A clip** (with 20% double-labelled for κ, and clinical disagreements settled by Rahmat, as now);
   - **a uniform random audit sample of stratum B:** 20%, at least 60 clips.

   **Blind:** the committee's answers are never shown to labellers.
4. **Gold:**
   - human labels for stratum A and the audit sample;
   - committee consensus for the rest of B.

   Every gold label records its source.
5. **Estimation, pre-registered here:**
   - every metric is computed on all 600 clips;
   - its 95% CI uses the stratified PPI estimator, with the audit sample correcting stratum B;
   - the human-only estimate (A + audit) and the uncorrected estimate are reported beside it.
6. **Safety stop:** if the audit finds missed danger signs in stratum B, with the upper 95% bound of that miss rate above 5%, humans label all of stratum B before the stage-2 freeze.
7. **Disclosure:** the benchmark card reports how many gold labels are human, how many are committee-labelled and audited, and the audit's results.

## Consequences
- **Human labelling falls from 720 labels to roughly the size of stratum A plus the audit.** That's an estimated 300–430 labels if 35–50% of clips land in A (the enriched sampling puts many danger signs in A). The real figure is known as soon as the committee runs.
- **Human time goes to the clips that decide the safety metric:** any possible danger sign, and any disagreement.
- **Labels already given in the review app are kept:** a human label always overrides the committee.
- **Cost:** about 3 GPU hours on Kaggle on 4 Oct.
- **A risk judges may raise:** "part of the gold is model-labelled." The PPI estimate, the audit and full disclosure answer it with numbers rather than assurances.
- **If Malik prefers all-human gold,** this ADR is rejected and the team labels all 600. The plan then depends on their pace.
