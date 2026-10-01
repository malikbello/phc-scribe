# Fine-tuning review: what the literature says about our problem

_1 Oct 2026. Written because the baseline and the pilot measured a specific failure, and the plan should rest on evidence rather than judgement. Proposals at the end need Malik's approval; none is applied yet._

## 1. The problem, as measured
- **Base N-ATLaS few-shot fails on about 1 in 5 items** (G: 57/300 schema-invalid; pilot: 6/30). Valid outputs are short (median about 890 characters); failed ones run on to whatever cap is set (768 or 1536 tokens, up to 5,052 characters) and end mid-string. Raising the cap changed **nothing** (pilot, identical metrics). This is a degenerate repetition loop, not a length limit.
- **It is weak even when valid:** danger-sign recall 0.73 on G, 0.60 on the pilot; false-alarm rate 0.19 and 0.39.
- **Its parent is much stronger at the same task:** Llama-3.1-8B-Instruct few-shot reaches recall 0.88 / 0.95 and false alarms 0.02 / 0.00 with 99% / 97% valid outputs.
- The task has to work in **Yoruba and Pidgin**, but our generated training notes (G) are **English only**.

## 2. What the literature says

### 2.1 The loop is a known effect of forcing JSON, and fine-tuning is the fix that works
- Grammar-constrained decoding guarantees valid tokens but cannot tell "the next distinct item" from "the same item again"; with greedy decoding a local model can lock onto one valid object and repeat it. Repetition penalties and sampling changes did not fix it; fine-tuning the model on gold JSON so it produces the format by itself did ([Coles, "Why local models get stuck repeating JSON"](https://coles.codes/posts/grammar-constrained-repetition-trap/), practitioner report, Qwen and Gemma families).
- Constrained decoding also has a "projection tax": when the model puts little probability on valid continuations, masking pushes it toward valid but wrong outputs. Drafting freely first and then constraining recovered **+24 points** on a 1B model (GSM8K 15.2% → 39.0%) ([Draft-Conditioned Constrained Decoding, arXiv 2603.03305](https://arxiv.org/abs/2603.03305)).
- **For us:** the base comparator's failure is partly *caused* by constrained decoding, which a reviewer could call an unfair baseline. Fine-tuning should remove most of the loop. We should also report the base model under unconstrained-then-parse decoding as a sensitivity check (proposal B).

### 2.2 Small amounts of good data are enough; the learning rate matters most
- Llama-3.1-8B-Instruct (N-ATLaS's base) fine-tuned with LoRA reached **human-level** structured extraction from clinical reports with **43–100 training reports** per task, 1–3 GPU hours each. Learning rate was the critical knob: **1e-4 gave 89.3%**, 1e-3 collapsed to 5.0%, 1e-5 reached 80.3% ([Human-level information extraction with fine-tuned language models, Sci Rep 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12749435)).
- On 60,000 clinical summaries, LoRA improved Llama-3.1-8B by 10–20 points over the base model and **QLoRA by 8–14, only 2–4 points behind LoRA** ([QLoRA vs LoRA for clinical data extraction, medRxiv 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12633606/)). QLoRA on a free T4 is a sound choice.
- **For us:** our config uses learning rate **2e-4**, twice the best value in the closest published setting (proposal A). A few hundred well-labelled examples should be enough; quality beats quantity.

### 2.3 LoRA protects general ability (G2)
- LoRA "learns less and forgets less": it underperforms full fine-tuning on the target domain but preserves out-of-domain ability better than weight decay or dropout, and targeting all transformer modules helps ([Biderman et al., TMLR 2024 / ICLR 2025](https://arxiv.org/abs/2405.09673)).
- **For us:** our QLoRA already targets attention and MLP modules (r = 16), so a small G2 regression is a realistic target. Keep it.

### 2.4 A pinch of the target languages transfers a lot
- Adding only **40 multilingual examples** to an English instruction-tuning set substantially improved instruction-following in seen *and* unseen languages; 2–4 languages in the mix improved cross-lingual generalisation ([Shaham et al., "Multilingual instruction tuning with just a pinch of multilinguality", 2024](https://arxiv.org/abs/2401.01854)).
- **For us:** training only on English G risks weak Yoruba/Pidgin behaviour. Even a modest number of real Yoruba and Pidgin examples should help a lot (proposal C).

### 2.5 A stronger model can label training data
- LLM "teacher labelers" produced labels good enough that distilled students **outperformed the teachers** and approached models trained on human labels in clinical extraction ([Distilling LLMs for efficient clinical information extraction, arXiv 2501.00031](https://arxiv.org/abs/2501.00031)); synthetic-data distillation let small open models match much larger ones on clinical extraction ([npj Digital Medicine 2025](https://www.nature.com/articles/s41746-025-01681-4)).
- **For us:** Llama-3.1-8B few-shot is already a strong teacher on our task (pilot recall 0.95, no false alarms). It can label unlabelled real speech from the **training** splits (WazobiaSpeech `train`, or MAMAI `train` if access arrives); keep only labels that pass our grounding (verbatim evidence) and schema checks; humans spot-check a sample (proposal D). **Licence to check first:** the Llama 3.1 Community License allows training on its outputs, but a distributed model trained that way must carry "Llama" in its name; N-ATLaS is itself Llama-based, so its own terms likely already require this.

### 2.5b A Nigerian precedent
- HelpMum fine-tuned Llama-3.1-8B-Instruct with LoRA on 36,000 maternal-health Q&A pairs (MamaBot-Llama); two Nigerian physicians rated it **4.9% better overall than the base model** (p < .001; +7% clinical trustworthiness, +5% medical accuracy) ([arXiv 2609.22110](https://arxiv.org/abs/2609.22110)). Same base family, same domain, same country: LoRA domain tuning works here, with gains that are real but modest, so honest reporting of a modest gain is normal.

### 2.6 How to set non-inferiority margins (G1, G2)
- Regulators require a margin justified on **both clinical and statistical grounds**; the FDA fixed-margin approach keeps at least **50% of the active control's effect** ([EMA guideline on choosing a non-inferiority margin](https://ema.europa.eu/documents/scientific-guideline/guideline-choice-non-inferiority-margin_en.pdf)). Expert surveys are an accepted way to set the clinical part.
- **For us:** G2 can follow the 50% rule exactly. N-ATLaS's whole point is its Yoruba gain over its parent Llama-3.1-8B, so the fine-tuned model should keep at least half of that gain on Belebele `yor_Latn`. G1 is a clinical tolerance (extra false referrals), so the nurse is the right person to confirm it (proposal E).

## 3. Proposals (need Malik's approval)
| | Change | Evidence | Scope |
|---|---|---|---|
| **A** | QLoRA learning rate 2e-4 → **1e-4**; if time allows, a 3-point sweep (5e-5, 1e-4, 2e-4) on the **dev** set only | §2.2 | Config change, within the approved architecture |
| **B** | Add a **supplementary** base comparator: N-ATLaS few-shot, unconstrained generation then parse. The pre-registered comparator (constrained, 768) stays primary | §2.1 | Eval addition; pre-registered before the freeze |
| **C** | Training mix: G (English, new seed) **plus real Yoruba and Pidgin examples** from training splits, never test speakers | §2.4 | Training data; covered by ADR-0016 §4 / ADR-0018 §6 |
| **D** | **Teacher labels:** Llama-3.1-8B few-shot labels real `train`-split health speech; keep only grounded, schema-valid outputs; spot-check 50 by hand; disclose in the model card | §2.5 | New training-data method: **needs an ADR** |
| **E** | **G2 margin = 50% of N-ATLaS's Belebele `yor_Latn` gain over Llama-3.1-8B**, capped at the approved 3 points (whichever is stricter). **G1** (+5 points) confirmed by Rahmat | §2.6 | Refines the approved margins; both models scored in one Kaggle job before the freeze |

## 4. What this changes in the plan
1. Before the freeze: one Kaggle job scores N-ATLaS and Llama-3.1-8B on Belebele `yor_Latn` (G2 base and the 50% rule) and runs proposal B on the pilot items.
2. Training data: G (new seed) + real Yoruba/Pidgin `train` examples, human-labelled where possible and teacher-labelled under D if approved.
3. QLoRA at 1e-4. Expect the loop to disappear; if invalid outputs persist after fine-tuning, that is a finding to report, not to hide.
