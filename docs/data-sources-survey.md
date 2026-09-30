# Data-source survey (after the AMR audit)

_Date: 29 Sept 2026. Time-boxed search of Hugging Face, Deep Learning Indaba / AfricaNLP / Masakhane, Intron Health, WAXAL and Meta Omnilingual. Licences and sizes come from each dataset card at the revision shown. "Access" means whether the `malikbello` HF token could download a data file._

## Bottom line
- **No public corpus of real Nigerian antenatal (ANC) encounter notes exists** that we could find. The African clinical text that is public is QA, vignettes, simulated conversations or guidelines.
- The strongest Nigerian material is from **Intron Health and partners**, including UCH Ibadan. It is simulated doctor–patient conversations, CHEW vignette QA, and **600 h of real maternal-health questions from Nigerian women in 7 languages**.
- So the benchmark has to be **constructed by clinicians, anchored in real language**. That is option (b)/(c) in `docs/data-audit.md` §4, and it needs a new ADR.

## Candidates
| Dataset | What it is | Size | Languages | License | Access | Use for PHC Scribe |
|---|---|---|---|---|---|---|
| [`intronhealth/NigBench-MAMAI-Speech-QA`](https://huggingface.co/datasets/intronhealth/NigBench-MAMAI-Speech-QA) ("Voices for Smart Care") @ `63b8620` | **Real** maternal/reproductive health questions spoken by women in rural and peri-urban Nigeria. Manually transcribed; informed consent stated; PII removed | 20,489 recordings, 600 h (Yoruba 4,082 / 100 h) | yo, ha, ig, pcm, ff, kr, nup | **CC-BY-4.0** | Gated (manual): **request** | **Top pick.** Real patient phrasing of pregnancy symptoms and danger signs, in Yoruba and Pidgin: (1) in-domain Yoruba ASR test set; (2) source of real symptom language for the benchmark and the lexicon; (3) S3 Yoruba slice |
| [`intronhealth/nig-bench`](https://huggingface.co/datasets/intronhealth/nig-bench) (AfriHealth-QA for frontline workers) @ `0c23662` | Situational vignette questions and answers for CHWs/CHEWs, written by 68 doctors; UCH Ibadan and UniJos collaborated | 9,303 answers / 7,289 questions (Yoruba 964, Hausa 653, Pidgin 412) | en, yo, ha, pcm, ig | CC-BY-NC-SA-4.0 | Gated (manual): **request** | Case seeds: ANC vignettes → clinician-written encounter notes. Also a PHC-QA regression check |
| [`intronhealth/med-convo-nig`](https://huggingface.co/datasets/intronhealth/med-convo-nig) @ `2c10faf` | 25 simulated tele-consultations by Nigerian clinicians, with audio and transcript. Includes **pre-eclampsia** and **hyperemesis gravidarum** | 4.2 h | en (Nigerian-accented) | CC-BY-NC-SA-4.0 | Gated (manual): **request** | Conversation → note demo and eval (the scribe's real input shape); a few ANC cases |
| [`intronhealth/afrispeech-dialog`](https://huggingface.co/datasets/intronhealth/afrispeech-dialog) @ `1beaa05` | 20 medical + 29 general simulated conversations (OSCE-style patient cards) | 7 h | en (African-accented) | CC-BY-NC-SA-4.0 | Open | ASR/diarization robustness; conversation → note format |
| [`intronhealth/AfriSwitchCare`](https://huggingface.co/datasets/intronhealth/AfriSwitchCare) @ `a9c91ab` | Code-switched doctor–patient conversations, 12 conditions × 9 languages (test only) | 108 conv., 12 h | incl. yo, ha, ig, pcm + en | CC-BY-NC-SA-4.0 | Gated (auto) | Yoruba–English code-switch eval. No ANC conditions |
| [`intronhealth/afrispeech-200`](https://huggingface.co/datasets/intronhealth/afrispeech-200) @ `b538c6e` | Accented English read speech, clinical and general domain | 200 h | en | CC-BY-NC-SA-4.0 | Open | Clinical-vocabulary ASR check |
| [`afrimedqa/afrimedqa_v2`](https://huggingface.co/datasets/afrimedqa/afrimedqa_v2) @ `3b4382f` | Pan-African medical MCQ and open QA (ACL 2025) | ~15k | en | CC-BY-4.0 | Open | General medical-knowledge regression check only |
| [`chisomrutherford/nigeria-clinical-guidelines-dataset`](https://huggingface.co/datasets/chisomrutherford/nigeria-clinical-guidelines-dataset) @ `94cac36` | Nigeria Standard Treatment Guidelines 2022, structured JSON (270 conditions) | 270 | en | CC-BY-4.0 | Open | Rule citations and grounding reference, next to the Standing Orders |
| [`google/WaxalNLP`](https://huggingface.co/datasets/google/WaxalNLP) @ `5f4d8ca` | General African speech corpus (ASR + TTS) | ~1,250 h transcribed | incl. yor, hau, ibo, pcm | CC-BY-4.0 / CC-BY-SA-4.0 | Open | General Yoruba ASR fine-tuning/eval. Not clinical |
| [`facebook/omnilingual-asr-corpus`](https://huggingface.co/datasets/facebook/omnilingual-asr-corpus) @ `8648ba8` | Spontaneous speech, 348 under-served languages | 3,350 h | many minority languages | CC-BY-4.0 | Open | Low relevance (Yoruba/Hausa are not its focus). Model family useful as an ASR baseline |
| [`IDinsight/urgency_detection_maternal_health_synthetic`](https://huggingface.co/datasets/IDinsight/urgency_detection_maternal_health_synthetic) @ `75bc14a` | LLM-generated maternal messages labelled for urgency (South African persona base) | ~12.8k | en | MIT | Open | Weak. Synthetic; possibly a danger-sign triage sanity check. Never benchmark data |
| AMR (audited) | 62 synthesized handwritten records | 62 | en | CC-BY-4.0 | Open | Real-style OOD/OCR slice (`docs/data-audit.md`) |

Looked at and not useful for the notes benchmark: "Dialogues of Delivery" (East African languages only), [Ajagbe's antenatal orientation speech set](https://www.researchgate.net/publication/385074850_Developing_Nigeria_Multilingual_Languages_Speech_Datasets_for_Antenatal_Orientation) (health-education scripts, en/yo/pcm, availability unclear), and the Indaba 2025/2026 "African Datasets" pages (not reachable from the dev environment; re-check from the laptop).

## Licence note (Track B is enterprise-facing)
The four Intron conversation and QA sets are **non-commercial (NC-SA)**. Using them for **evaluation** in a competition entry is inside the licence. **Training** a model we may later commercialise on them is not. So train only on CC-BY material and our own data; use NC sets for evaluation, and say so in the benchmark report. NigBench-MAMAI is CC-BY-4.0, so training is fine with attribution.

## Proposed benchmark composition (for the ADR; Malik decides)
1. **Core, 500+ items:** ANC encounter notes and dictations written by the nurse and the medical student from structured case cards. Cards are seeded from nig-bench ANC vignettes and Standing Orders scenarios. Danger-sign phrasing comes verbatim from NigBench-MAMAI real transcripts where possible. Reported as *clinician-constructed*.
2. **Real-language slices:** NigBench-MAMAI Yoruba/Pidgin test transcripts. Symptom and danger-sign extraction from real patient speech, labelled by the team.
3. **Conversation slice:** med-convo-nig (the pre-eclampsia and hyperemesis conversations) plus afrispeech-dialog, for conversation → note.
4. **OOD slice:** AMR (62 records).

## Round 2 (29 Sept): Deep Learning Indaba, Masakhane, ML Collective, Nigerian teams
_Scope: Indaba 2025 (Kigali) and 2026 (Nigeria) posters, papers, DS4Health workshop and African Datasets pages; AfricaNLP 2025/2026; the Masakhane HF org; ML Collective; Lacuna Fund; HF org catalogues (Intron, HelpMum, DSN, NCAIR1, Lelapa, Sunbird, CLEAR Global, McGill-NLP); Kaggle. The dev environment blocks deeplearningindaba.com, arXiv, ACL Anthology, OpenReview and OSF, so those were read through search snippets and GitHub sources. **Malik should open the Indaba "Posters" and "African Datasets" pages for 2025 and 2026 in a browser.** Their full lists could not be read here._

**Finding:** there is real Nigerian PHC and maternal data. It is **held by teams, not openly published as notes.** The published parts that fit us:

| Source | What it is | Why it matters | How to get it |
|---|---|---|---|
| **IyàwóBench v1/v2** ([arXiv 2605.23465](https://arxiv.org/abs/2605.23465), [v2 2607.29085](https://arxiv.org/html/2607.29085)) | 200 vignettes for LLM triage in **Nigerian PHCs**. Fields: vitals, **BP**, WHO IMCI danger-sign checklist, **pregnancy status**, **free-text clinical notes**; triage labels REFER NOW / REFER TODAY / TREAT HERE. Generated from the distributions of **1,200 real encounters at 19 PHCs in Oyo State (Apr 2026)** | Closest match to our task: same state as UCH, CHEW setting, danger signs and triage. The team holds real PHC encounter data | Check the paper for a data link (arXiv is blocked here). **Contact the authors** about evaluation-only access or a collaboration |
| **HelpMum** (Ibadan): [`HelpMum-Personal/MamaBench`](https://huggingface.co/datasets/HelpMum-Personal/MamaBench) ([arXiv 2607.14385](https://arxiv.org/abs/2607.14385)); MamaBot-Llama ([arXiv 2609.22110](https://arxiv.org/abs/2609.22110)) | MamaBench: 217 counterfactual **maternal and child health vignette pairs** (CC-BY-4.0, gated with automatic approval: accepting the terms gives access immediately). MamaBot was trained on **36k Nigerian maternal-health QA pairs**, rated by Nigerian physicians | Maternal diagnostic reasoning tuned to Nigeria. Their QA data could be a training source, and they are an obvious partner | Accept the MamaBench terms on HF. Ask HelpMum about the 36k QA set |
| **St Luke's Anua MNCH records** ([F1000 11:166](https://f1000research.com/articles/11-166/v2); data at [OSF j9zh8](https://doi.org/10.17605/OSF.IO/J9ZH8)) | **538 real maternal records** (plus 720 neonatal, 425 child) from a Nigerian hospital, 2014–2019. Structured, for spatiotemporal analysis | Real Nigerian distributions (age, parity, complications) to seed realistic ANC case cards | Download from OSF (open part). Check the licence. GPS data is by request only |
| Indaba 2025 posters (seen via search) | "Ensembled-Based Model for Predicting Maternal Health Risk in Southwest Nigeria"; "UlizaMama: Maternal Health LLMs" (Kenya); "Safe mom" risk prediction; DS4Health workshop (Intron, Jacaranda, Google) | Southwest Nigeria maternal-risk data (probably tabular) | Find the authors or the dataset from the posters page |
| Indaba 2026 posters (Nigeria) | "Triaging Maternal Health LLMs With Hierarchical Intent Models"; Nigerian TB and stunting ML | Maternal triage-intent data | Same |

**Masakhane:** no clinical or maternal dataset in its HF org (`AfriADR` is diacritic restoration, not adverse drug reactions). Useful side resource: [`masakhane/AfriDocMT`](https://huggingface.co/datasets/masakhane/AfriDocMT) (334 health documents human-translated into Yoruba and Hausa), for Yoruba medical terms. **ML Collective:** a research community with no dataset catalogue; nothing health-specific found. **Lacuna Fund:** the 2023 maternal-health awards include a prenatal risk-categorisation dataset (country unconfirmed) and ABreast (Nigeria/Uganda ultrasound). Nothing note-shaped. **Kaggle:** tabular or QA only (e.g. Naija Health Q&A, Rivers State). Nothing note-shaped. **Excluded:** `Ajisco/redacted-clinical-notes` (US-style synthetic notes, not Nigerian); `electricsheepafrica/*` (catalogue/synthetic).

### What changes
- The benchmark design stays **clinician-constructed ANC notes anchored in real data**. The anchors are now stronger: real maternal distributions (St Luke's MNCH), real PHC vignette structure (IyàwóBench), real maternal phrasing (NigBench-MAMAI) and Nigerian maternal QA (HelpMum).
- **Partnership route (highest upside):** the Iyàwó team (Oyo PHCs) and HelpMum (Ibadan) both hold real Nigerian primary-care or maternal data, near UCH. An evaluation-only data-use agreement or collaboration could give real items before 12 Oct; that timing is not guaranteed. Ask now, in parallel with the constructed benchmark.

## Round 3 (29 Sept): hands-on checks
- **IyàwóBench** ([repo](https://github.com/anthoniooladimeji11-coder/iyawobench) @ `6b0006c`, **CC BY 4.0**): 200 vignettes (`v1/iyawobench_v1.csv`).
  - Content: febrile illnesses only (malaria, sepsis, meningitis, pneumonia, typhoid). **18/200 pregnant, 0 ANC visits.**
  - The `notes` field is one of about 13 templated sentences, often empty. Some values are implausible (e.g. an adult of 27.7 kg).
  - **Use:** format reference for vitals and triage labels; possibly a small general-PHC triage regression check. **Not ANC data.**
- **MamaBench** (@ `d85c704`, **CC-BY-4.0**, access granted):
  - 434 first-person clinician-authored vignettes, median 56 words, with a diagnosis label (371 distinct).
  - Our heuristics: primary visit type child 196, unknown 101, **ANC 78**, delivery/postnatal 55. **37 ANC vignettes contain a danger sign.** Gestational-age mentions in 68, BP in 18.
  - **Use:** case-card seeds for the authored ANC benchmark (attribution required); pairs stay within one split.
- **Intron gated sets** (`NigBench-MAMAI-Speech-QA`, `nig-bench`, `med-convo-nig`): HF still says **"awaiting a review from the repo authors"** for account `malikbello` (checked 29 Sept, late afternoon).
- **Proposal:** ADR-0016 (Proposed). The core benchmark is team-authored and licence-clean; MAMAI is a real-language stratum; NC sets are evaluation-only; real clinical data is upside, not a dependency.

## Actions
- Malik: request access on HF to `NigBench-MAMAI-Speech-QA`, `nig-bench` and `med-convo-nig` (manual approval can take days, so do it today). Accept the MamaBench terms (instant access).
- Malik: email the IyàwóBench authors and HelpMum about evaluation-only access or collaboration. Download the St Luke's MNCH data from OSF.
- Malik: open the Indaba 2025/2026 Posters and African Datasets pages in a browser, and flag anything with clinical text.
- Then re-run the survey access checks and run the audit tooling over the accessible sets.

## Round 4 (30 Sept): WazobiaSpeech, Kitala AI

**WazobiaSpeech** (EqualyzAI / Data Science Nigeria, Interspeech 2026): about 2,500 h of transcribed speech in Pidgin, Yoruba, Igbo and Hausa on Hugging Face under `Africanvoice/` (the repos with data are `African_voices_naija`, `african_voice_yoruba`, `African_voices_igbo`, `hausa_african_voices`). Ungated. The Pidgin, Igbo and Hausa cards say CC-BY-4.0; the Yoruba card states no licence (to confirm with the authors). Clips carry a `domain` tag, and **`HE` (health) is a large share**: in the Pidgin dev + dev_test splits, 5,591 of 35,061 clips are health, and 421 of those mention pregnancy or danger-sign terms (for example "syphilis fit pass through mama to pikin when she get belle"). About half the clips in the first Yoruba dev shard are health, mostly spontaneous speech ("ó ti ń dà nù fún nǹkan bí oṣù kan").

- **What it is:** real, consented, unscripted single-sentence speech about health. It is not visit narratives and has no clinical labels.
- **Useful for:** (1) a real-speech ASR test of the N-ATLaS Yoruba/Pidgin ASR on health talk; (2) mining real Pidgin/Yoruba wordings for the phrase bank and lexicon (open question 7); (3) a candidate **hard-negative stratum**: real sentences that mention danger-sign words but are general statements, not a patient's findings, which tests false alarms. Using (3) in the counted benchmark would change ADR-0016, so it needs a new ADR and Malik's OK.

**Kitala AI** (kitala.ai, by YUX Design): a commercial data-collection and LLM-testing service using field surveyors. It publishes no open datasets. It would be a paid service, so it is out under the $0 budget. The site itself is blocked from the cloud session.

## Round 5 (30 Sept, evening): real-data alternatives to NigBench-MAMAI
Question: if Intron does not grant MAMAI access, is there other **real**, licence-clean Nigerian data for the counted ANC benchmark? Hugging Face was searched (maternal, antenatal, pregnancy, Nigerian/Yoruba/Pidgin/Hausa health, AfriSpeech, AfriMed, Naija, Wazobia; 277 hits, mostly national statistics, synthetic sets or other countries). Access re-checked the same day: `NigBench-MAMAI-Speech-QA` and `nig-bench` are still 403; `med-convo-nig` is open.

| Source | Real? | Licence / access | ANC content (measured) | Verdict |
|---|---|---|---|---|
| **WazobiaSpeech**, now `Africanvoice/{yoruba,naija,igbo,hausa}_african_voices` (repos renamed since round 4) | Real, spontaneous speech | **CC-BY-4.0 on all four cards, Yoruba included** (Yoruba card updated 30 Sept; round 4 found no licence); ungated | Yoruba `dev_test` shard 0: 64/342 clips are health (`HE`), all spontaneous, first-person symptom talk ("ìrora náà pọ̀ débi pé ó ṣòro fún mi láti mí"); 7 hit pregnancy/blood/doctor terms. Pidgin shard 0: 65 health, 11 pregnancy terms, mostly general statements ("if you de schedule appointment early e go better for mama and pikin") | **Best non-Intron real source.** Real patient-style speech, but ANC-positive items are sparse, so danger-sign recall would rest on few positives. Using it as the counted set changes ADR-0016 and needs a new ADR. |
| **AfriMed-QA v2** (`afrimedqa/afrimedqa_v2`) | Human-written, but in answer to **made-up scenarios** ("Your friend … what should she ask her doctor?") | CC-BY-4.0, open | 10,000 consumer queries; 417 pregnancy-related, 221 from Nigerian contributors; 1,008 obstetrics/gynaecology items (387 Nigerian) | Prompted, so not "real data" under the NAIC rule. Useful supplement (English, question form). |
| **NaijaMed-QA** (`Ayomidejoe/NaijaMed_QA_Dataset`) | Real questions from a Nigerian health forum, 2018–2022 | Uploader says MIT; taken from a MySQL dump of a closed platform, consent and platform terms not stated | 1,685 questions; 281 pregnancy-related (many about contraception); category "Pregnancy" = 150 | Provenance too unclear for the counted set. At most an evaluation-only supplement, after asking the uploader. |
| `intronhealth/med-convo-nig` | Recorded conversations | CC-BY-NC-SA-4.0, access granted | 25 recordings in total, one on pre-eclampsia | Too small. |
| `Data-Science-Nigeria/voice-of-care-health-dataset` | Real health speech | CC-BY-4.0, open | Hausa only (30,000 clips) | Out of scope unless Hausa is added. |
| AfriSpeech-200 / AfriSpeech-Dialog, NaijaVoices | Real speech | CC-BY-NC-SA-4.0 | General clinical/accented English; not ANC | Evaluation only at most; not ANC. |

**Conclusion:** Intron is not the only real source. If MAMAI does not arrive, the strongest fallback is **WazobiaSpeech Yoruba + Pidgin health clips** (real, consented, CC-BY, open), with G, MamaBench and AfriMed-QA pregnancy queries as labelled supplements. That keeps the counted benchmark real instead of falling back to MamaBench + G. It changes ADR-0016 §6, so it needs a new ADR and Malik's approval.
