# ADR-0024: Fine-tuning recipe: data first, failure-targeted objectives, evaluated as shipped

- **Status:** Accepted by Malik, 2 Oct 2026.
- **Date:** 2026-10-02
- **Changes:** extends architecture §6 (QLoRA) and `configs/qlora.v0.yaml`. Builds on ADR-0004 (constrained decoding and grounding), ADR-0009 (evaluate what we ship), ADR-0021 (teacher labels) and ADR-0022 (two-stage freeze). The pre-registered metrics and margins (`docs/eval-plan.md` §6) do **not** change.

## Context

### What the judges reward
The criteria (`docs/naic-requirements.md`) map onto training like this:
- **Technical rigour (1):** a reviewer must be able to see *why* each training choice was made and that no test data shaped it.
- **N-ATLaS integration depth (2):** fine-tune N-ATLaS itself, and use N-ATLaS ASR inside the pipeline, not only in a demo.
- **Real-world validation (3):** the gain must hold on the real 500+ set, in Yoruba as well as English, for the Q4 file we ship.
- **Impact and scalability (4, 5):** a recipe that adds a language or a danger sign without re-engineering.

### What we have measured
Each problem is a finding from our own runs, not an assumption.

| # | Problem | Evidence |
|---|---|---|
| F1 | Base N-ATLaS loops under constrained decoding: about 1 in 5 outputs never close | G 57/300 invalid; pilot 6/30 at both 768 and 1,536 tokens; H 47/454 |
| F2 | It invents findings | False-alarm rate: 0.187 on G; **0.185 [0.122, 0.247] on 454 real hard negatives (H)** |
| F3 | It misses danger signs that its parent catches | Recall 0.735 vs Llama-3.1 0.876 on G |
| F4 | **The real Yoruba/Pidgin training labels cover the rarest danger signs barely or not at all** | Of 460 kept teacher labels: reduced fetal movement **0**, unconscious **0**, convulsions **2**, severe abdominal pain **2** |
| F5 | **The teacher systematically over-assigns "looks very ill"** | 42 of 131 danger-sign items. Read by hand, most evidence is general talk, questions or even negations ("kò sí koko kankan, kò sí oyun kankan": "no lump, no pregnancy"). By definition the sign needs a health worker's statement; these clips are patient or general speech. Training on them teaches false alarms (G1) |
| F6 | The shipped input is ASR output, but the training text is human transcripts | Architecture: audio → N-ATLaS ASR → extraction; teacher labels are on WazobiaSpeech transcripts |
| F7 | Fine-tuning can erode N-ATLaS's general Yoruba (G2) | Belebele `yor_Latn`: N-ATLaS 42.78% vs Llama-3.1 34.44%; margin m = 3 points |
| F8 | Q4 quantisation can undo part of a gain (ADR-0009) | The headline result is the Q4_K_M GGUF |

### Do we need new mathematics or a new fine-tuning architecture?
**No.** Every problem above is a known failure mode with a known, validated fix. A new architecture would add an untested component nine days before submission, and judges reward a working, validated build over novelty. What separates a mature team from a tutorial is not the adapter type, since mature teams use LoRA/QLoRA too. It is:
1. data built against measured failures;
2. a training objective aimed at the errors that matter clinically;
3. decoding guards that make some failures impossible;
4. evaluating the exact file that ships.

The recipe below does all four. Its one modelling change beyond plain SFT, a safety-weighted token loss, is standard cost-sensitive learning (weighted empirical risk), applied to the tokens that carry clinical meaning.

## Decision

### Stage 0: data (the biggest lever)
1. **Teacher-label audit per concept, beyond ADR-0021's 50-clip check:**
   - Apply the ontology's speaker-role rule deterministically: **`looks_very_ill` cannot come from patient or general speech.** Teacher findings of it on WazobiaSpeech are removed, and the item is re-checked for other findings (F5).
   - Report each concept's precision in the 50-clip check. Any concept below 0.8 is dropped from teacher labels, not only judged on the overall 1-in-5 rule.
2. **Rare danger signs in Yoruba and Pidgin (F4):** a small, controlled set of synthetic yo/pcm utterances for the under-covered signs, about 15 per sign:
   - reduced fetal movement;
   - unconscious;
   - convulsions;
   - severe abdominal pain;
   - plus negated and hedged versions ("ọmọ ń mì dáadáa" style), so the model learns the cue, not the word.

   **Malik writes or approves the Yoruba; Rahmat approves the clinical meaning.** Built from the phrase bank and `lexicon.v0.yaml`, tagged `origin: synthetic-phrasebank`, capped at 15% of training, and reported in the model card. Never used for testing.
3. **Train on what the model will actually read (F6):**
   - run N-ATLaS ASR (NCAIR1 yo/pcm) over the training audio;
   - train on **both** views of each clip, the human transcript and the ASR hypothesis, with the same gold record;
   - the gold evidence quote is re-located in the ASR text, and dropped if it can't be found.

   Precedent: training on ASR hypotheses improves spoken extraction robustness (MEDSAGE, AAAI 2025; n-best slot filling, +4 F1). This also puts N-ATLaS ASR *inside* the trained system (criterion 2).
4. **Quiet examples (F2):** teacher items with no finding stay, capped at half of the teacher set (ADR-0021), so the model learns to output an empty record.
5. **Dev split, decided now:** 15% of the training sources held out **by speaker and group**. Every recipe decision below (weights, scale, whether stage 2 is used) is made on dev only. The test set is never read.

### Stage 1: supervised fine-tuning, with two targeted changes
- **Unchanged:**
  - QLoRA on `NCAIR1/N-ATLaS`;
  - all attention and MLP modules (LoRA "learns less and forgets less" when all modules are targeted);
  - r = 16, α = 32;
  - lr 1e-4 (proposal A);
  - 2 epochs;
  - assistant-only loss;
  - the short fine-tuned prompt.
- **Safety-weighted token loss (F2, F3):** the JSON answer is mostly boilerplate (braces, keys, empty lists). Plain SFT spreads the gradient evenly over it, which dilutes learning on the few tokens that decide safety (the TAB-PO paper names this "gradient dilution"). We weight the per-token cross-entropy:

  $$\mathcal{L} = \frac{\sum_t w_t \, \ell_t}{\sum_t w_t}, \qquad w_t = \begin{cases} w_c & t \in \text{concept or assertion value} \\ 1 & \text{otherwise} \end{cases}$$

  - with $\ell_t = -\log p_\theta(y_t \mid y_{<t}, x)$;
  - token membership comes from the tokenizer's character offsets over the gold JSON;
  - $w_c \in \{1, 3\}$ is chosen on dev, where $w_c = 1$ is plain SFT, so the ablation is built in.
- **Bounded output (F1):**
  - `maxItems` on `findings`, `anc.tests` and `anc.medications` (10 each);
  - the grammar then makes an endless list impossible for every system;
  - it is applied identically to all rungs, base included, and fixed in the eval plan **before** the stage-1 freeze, which makes the base comparator fairer, not weaker.

### Stage 2: on-policy preference optimisation, only if dev still shows false alarms or missed signs
- **Sample the stage-1 model** on the training and dev-train items.
- **Build pairs only where its own output differs from gold on a critical field:**
  - a finding not in gold (false alarm);
  - a danger sign missed;
  - a wrong assertion (present vs absent).

  Chosen = gold; rejected = the model's own output. On-policy negatives work better than synthetic ones (OPA-DPO, CVPR 2025), and minimally different, schema-valid negatives target exactly the deciding tokens (TAB-PO, 2026).
- **DPO** with the LoRA reference (adapters off, so no second model in memory), β chosen on dev:

  $$\mathcal{L}_{\text{DPO}} = -\log \sigma\!\left(\beta \log \frac{\pi_\theta(y_w \mid x)}{\pi_{\text{ref}}(y_w \mid x)} - \beta \log \frac{\pi_\theta(y_l \mid x)}{\pi_{\text{ref}}(y_l \mid x)}\right)$$

- **Adopted only if dev improves** danger-sign recall without raising false alarms. Otherwise stage 1 ships, and the result is reported.

### Stage 3: forgetting control (F7)
- The merged weights are $\theta = \theta_0 + s \cdot BA$, the LoRA delta scaled by $s \in \{0.5, 0.75, 1.0\}$. This is the weight interpolation of WiSE-FT applied to a LoRA delta.
- **Choose $s$ on dev:** highest task score whose Yoruba perplexity, on a held-out general Yoruba text (not Belebele, which stays the untouched guardrail test), is within 2% of base.
- **Scale is fixed before the test set is scored.**

### Stage 4: quantise for what ships (F8)
- Merge → GGUF → **Q4_K_M with an importance matrix computed on training-split transcripts** (llama.cpp `llama-imatrix`).
- On dev, compare Q4 with and without the imatrix; keep the better.
- The headline benchmark runs on that Q4 file (ADR-0009). The full-precision model is reported beside it, so the quantisation loss is visible.

## Run budget (Kaggle T4, started by Malik from the editor)

| Run | Purpose | GPU time (est.) |
|---|---|---|
| A | N-ATLaS ASR over training audio (both views) | ~1 h |
| B | Stage 1 SFT, $w_c = 1$ (plain) | ~1.5 h |
| C | Stage 1 SFT, $w_c = 3$ (weighted): **ablation pair with B** | ~1.5 h |
| D | Dev scoring of B and C, sampling for stage 2 | ~1 h |
| E | Stage 2 DPO (only if needed) | ~2 h |
| F | Merge at chosen $s$, GGUF + imatrix, dev check of Q4 | ~1.5 h |
| G | Final scoring: base vs fine-tuned Q4 (+ full precision) on every stratum, Belebele G2 | ~3 h |

About 12 h in total, within the weekly free quota. Runs A–D can be prepared before the stage-1 freeze, but no training data is built until it.

## Timeline
| Date | Step |
|---|---|
| 2–4 Oct | Malik's 50-clip check · the concept audit applied · the phrase-bank yo/pcm set written and approved · `maxItems` added (all rungs) · weighted loss, two-view data, pair builder and scaled merge implemented with tests |
| 5 Oct | Stage-1 freeze (items) → build the training set → runs A, B, C |
| 6 Oct | Run D: choose $w_c$, decide on stage 2 → run E if needed |
| 7 Oct | Run F: choose $s$, quantise, dev check |
| 8–9 Oct | Labelling settled → stage-2 freeze (labels) → run G |
| 10–11 Oct | Benchmark report, model card (with ablations and failures), demo, submission |

## Note, 4 Oct 2026: the ASR view comes from the shipped ASR
ADR-0026 replaced the base N-ATLaS ASR with fine-tuned models, so the two-view training data now uses the fine-tuned transcripts (`data/private/kaggle/asr-ft-train.jsonl`). The LLM trains on the kind of text it will receive in service.
- **Out-of-sample:** the 460 training clips were excluded from the ASR fine-tune, so their transcripts are not memorised.
- **WER on these clips:** Pidgin 23.6% and Yoruba 33.0%, against 53.1% and 36.1% for the base ASR.
- **Yield:** 349 ASR views from 376 audited teacher items (333 with the base ASR).

## Consequences
- **Each measured failure has a named countermeasure and a dev-set ablation,** so the report can show what helped and by how much: the rigour judges look for.
- **More N-ATLaS integration:** N-ATLaS ASR is part of the trained system, not just the demo.
- **The rare-sign phrase-bank set is synthetic.** It is disclosed, capped, and reviewed by a clinician and a native speaker.
- **Risk:** the timeline depends on labelling finishing by 8 Oct and on Malik starting each Kaggle run.
- **Stop rule:** if stage 1 alone meets P1/P2 on dev, stages 2–3 are skipped rather than added for show.
- **Anything that fails on the test set is reported as failed** (eval plan §6).

## References
- Biderman et al., "LoRA Learns Less and Forgets Less", TMLR 2024: https://arxiv.org/abs/2405.09673
- TAB-PO, token-level preference optimisation for structured generation, 2026: https://arxiv.org/abs/2603.00025
- OPA-DPO, "On-policy data hold the key", CVPR 2025: https://github.com/zhyang2226/OPA-DPO
- Rafailov et al., Direct Preference Optimization, NeurIPS 2023: https://arxiv.org/abs/2305.18290
- Wortsman et al., WiSE-FT, robust fine-tuning by weight interpolation, CVPR 2022: https://arxiv.org/abs/2109.01903
- FLOW, upweighting easy samples mitigates forgetting, 2025: https://arxiv.org/abs/2502.02797
- MEDSAGE, robustness of medical dialogue summarisation to ASR errors, AAAI 2025: https://ojs.aaai.org/index.php/AAAI/article/view/34518
- Speech-based slot filling with LLMs (n-best hypotheses): https://arxiv.org/abs/2311.07418
- llama.cpp importance-matrix quantisation (Sunbird SALT guide): https://salt.sunbird.ai/sunflower/quantization/
- Clinical extraction with LoRA on Llama-3.1-8B (learning rate, data size): `docs/research/finetuning-review.md` §2.2
