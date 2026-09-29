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

## Actions
- Malik: request access on HF to `NigBench-MAMAI-Speech-QA`, `nig-bench` and `med-convo-nig` (manual approval can take days, so do it today).
- Then re-run the survey access checks and run the audit tooling over the accessible sets.
