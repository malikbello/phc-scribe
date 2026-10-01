# ADR-0020: Use the Antenatal Orientation Speech Dataset for hard negatives, ASR and phrases

- **Status:** Accepted by Malik, 1 Oct 2026
- **Date:** 2026-10-01
- **Adds:** a reported stratum (H) to `docs/eval-plan.md` §3 and an ASR test. The counted benchmark is unchanged (ADR-0016 / ADR-0018).

## Context
- Ajagbe S. A. (2024), "Developing Nigeria Multilingual Languages Speech Datasets for Antenatal Orientation", Springer CCIS (Applied Informatics), doi 10.1007/978-3-031-75147-9_11. Data on GitHub `Adeola80/Antenatal-Speech`, **MIT licence** (© 2024 Ajagbe Sunday Adeola). Downloaded 1 Oct.
- Contents: one antenatal orientation talk recorded in Nigerian antenatal clinics, as text and speech in **English, Yoruba and Pidgin** (parallel translations; about 2,600 / 3,200 / 2,500 words; one recording of about 17 minutes per language, 128 kbps MP3). The talk covers the signs of pregnancy, its stages, diet, drugs, problems and what to do.
- It is a **health worker teaching**, not women reporting their own symptoms. Under our guidelines (record only what the woman herself reports), every sentence has **no finding**, yet many sentences mention symptoms and danger signs ("Some go dey vomit", "small pain for the down side of the belle").
- The README does not state how consent was obtained. The speakers are health workers giving a public-health talk, not patients.

## Decision
1. **Stratum H (hard negatives, reported, not counted):** each sentence of the three transcripts becomes an item with an **empty gold record**, `origin = real`. Measured: the **false-finding rate** (share of sentences where the system records any finding as present or possible) and the **false-flag rate** (share that raise any danger flag). Reported per language with exact 95% CIs. The sentences of one talk are not independent, which the report says. Built by `scripts/build_adeola_items.py` into `data/bench/h.adeola.jsonl`, with the MIT notice beside it.
2. **ASR test:** the three recordings through N-ATLaS ASR, word error rate against the transcripts (approximate: the transcripts are lightly edited and the audio is one long file). Reported, not counted.
3. **Phrase mining:** symptom wordings in Yoruba and Pidgin go to the phrase bank and lexicon, reviewed by Malik.
4. **Not used for training.** H stays a test of what the model must *not* do.

## Consequences
- A real-language check of the most dangerous error for a scribe: writing down a symptom the patient never reported. It costs nothing and needs no labelling.
- Small: one talk per language, about 150–200 sentences each. Results are indicative.
- Attribution in the benchmark report and dataset card; the MIT notice travels with the derived file.
