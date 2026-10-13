---
license: other
license_name: n-atlas-terms-of-use
base_model: NCAIR1/N-ATLaS
language: [yo, pcm, en]
tags: [gguf, llama.cpp, n-atlas, health, nigeria, antenatal-care, clinical-documentation]
---

# N-ATLaS Health ANC Scribe · Q4_K_M GGUF · Powered by Awarri

A fine-tune of [N-ATLaS 8B](https://huggingface.co/NCAIR1/N-ATLaS) that turns an antenatal visit, spoken in **Yorùbá, Nigerian Pidgin or English**, into a structured record:
- findings, with the words each came from;
- measurements;
- the facts the danger-sign rules check.

It is the note model of **PHC Scribe** and the **Tákàdá** app, an offline scribe for Nigerian primary health centres (NAIC 2026, Problem Statement 3).

| | |
|---|---|
| File | `natlas-qlora-v1-weighted-fs.Q4_K_M.gguf`, 4.9 GB, imatrix Q4_K_M |
| Runtime | llama.cpp (tested at b11387, CPU only); about 5.5 GB RAM with the 8,192-token context |
| Speed | A record in about 2 minutes on a 4-core laptop CPU (median of 8 notes) |
| Base | `NCAIR1/N-ATLaS` @ `e294476` |

## Intended use
- **Drafting** the record of an antenatal visit for a health worker to check and confirm, inside PHC Scribe: its prompt, its JSON schema as a grammar, then grounding, the polarity check and the danger-sign rules.
- **Not for:**
  - deciding on danger signs (deterministic rules do that, from the confirmed facts);
  - diagnosis;
  - use without a health worker confirming the record;
  - conditions outside antenatal care.

## Training
- **Method:** QLoRA (rank 16), loss weighted ×3 on the concept and assertion tokens, trained with the base model's own few-shot prompt (ADR-0024, run C-fs). The run was chosen on dev (127 items) and pilot (30) data only; no test item was seen.
- **Data: 685 examples.**
  - **588 real:** WazobiaSpeech training speakers (CC-BY-4.0), health clips; labels audited per concept by a teacher model and the team (ADR-0021, ADR-0024). Includes versions passed through the fine-tuned speech recognition, so the model trains on the text it will receive.
  - **97 generated:** controlled statements for danger signs that real speech barely covers, checked by rules and a round trip (ADR-0028), and capped.
  - **By language:** Yorùbá 321, Pidgin 290, English 74.
- **Never in training:** any test item. The two-stage freeze (ADR-0022) hashed the test items before training data was built.
- **Quantisation:** merged, then Q4_K_M with an importance matrix computed on training text only.

## Evaluation (pre-registered; this file against base N-ATLaS with the same prompt)
| Test | Base | This model | Difference [95% CI] |
|---|---|---|---|
| Danger-sign recall, Yorùbá statements (S5) | 52.6% | **67.9%** | +15.4 [+4.8, +26.4] |
| Danger-sign recall, Pidgin statements (S5) | 68.0% | **76.9%** | +9.0 [+1.3, +17.2] |
| Danger-sign recall, English notes (G) | 80.2% | **91.0%** | +10.7 [+4.0, +17.6] |
| False alarms, 454 real antenatal teaching sentences (H) | 15.9% | **9.3%** | −6.6 [−10.8, −2.7] |
| False alarms, 570 real Yorùbá and Pidgin health speech clips (S4-W) | 26.5% | **13.2%** | −13.3 [−15.9, −11.0] |
| General Yorùbá (Belebele, 900) | 42.9% | 42.2% | −0.7 [−2.1, +0.8] |

- All four pre-registered criteria pass.
- S5 and G were constructed for the benchmark, because real speech has too few danger signs to measure recall. H and S4-W are real.
- Full method and intervals: the PHC Scribe benchmark report.

## Limits and risks
- **It misses danger signs:** about 1 in 3 in Yorùbá statements and 1 in 4 in Pidgin. On real recorded speech there is early evidence only: one recorded test visit run five times end to end, with bleeding found 5 of 5 times and severe headache 4 of 5.
- **It can raise a sign the speaker denied** (for example "the baby moves well" drafted as reduced movement). PHC Scribe flags such findings for checking.
- **Evaluated on antenatal care only,** in Yorùbá, Pidgin and English; Hausa and Igbo are not evaluated.
- **Not used yet with real patients in a clinic.**
- **A 3-bit version was tried and rejected:** it missed too many danger signs on dev data.

## Use
Use it with PHC Scribe's few-shot prompt and JSON schema (`serve/phc_scribe`). Decode greedily, with repetition penalty 1.12 and an 8,192-token context. The clinic hub serves it with llama.cpp `--jinja`.

## Licence
- This derivative is governed by the **N-ATLaS Terms of Use**: the "Powered by Awarri" naming, and the limit on active users without a commercial licence from Awarri Technologies.
- N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, powered by Awarri Technologies.
