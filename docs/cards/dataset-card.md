# PHC-Scribe-Bench v0: dataset card

The benchmark behind PHC Scribe's results. It measures structured antenatal extraction and danger-sign detection in **Yorùbá, Nigerian Pidgin and English**, against base N-ATLaS. Pre-registered in `docs/eval-plan.md`. Frozen in two stages: items, then labels (`data/bench/test-manifest.json`).

## Sets
| Set | Items | Language | Origin | Gold labels | Licence of the source |
|---|---|---|---|---|---|
| **S5** patient statements | 300 (156 with a danger sign) | 150 yo, 150 pcm | Constructed from a fixed lexicon of first-person clauses (present, denied, hedged, past), independent of every compared model and of the labelling committee | By construction | Ours |
| **G** antenatal notes | 300 (226 with a danger sign) | en | Generated (`bench/notegen.py`) | By construction | Ours |
| **H** hard negatives | 454 | 148 en, 158 yo, 148 pcm | Real antenatal teaching sentences (Ajagbe 2024) | No finding, by source | MIT |
| **S4-W** health speech | 600 (570 scored) | 300 yo, 300 pcm | Real WazobiaSpeech `dev` and `dev_test` health clips | A model committee on every clip, plus a seeded human sample (ADR-0025) | CC-BY-4.0 |
| **R** red team | 36 | mixed | Constructed adversarial cases | By construction | Ours |
| **Belebele** `yor_Latn` | 900 | yo | Real (Meta) | Multiple choice | CC-BY-SA-4.0 |

## Labels
- **Schema:** each record is a list of findings (concept, assertion, evidence quote) plus measurements, in the encounter schema `schema/encounter.v0.1.json`, against a vocabulary of antenatal concepts (`schema/vocab/`).
- **Danger signs:** 14 concepts, with rules in `rules/danger_signs.v0.yaml`.
- **Annotation guidelines:** `docs/annotation-guidelines.md`. On S4-W, general talk is "Nothing to record", and only garbled, cut-off or other-language clips may be skipped.
- **S4-W human labels:**
  - 120 clips labelled by the nurse Rahmat, 36 also by Malik Bello; 25 of 25 overlapping labels agree;
  - 11 skip-versus-label disagreements were settled by the pre-registered clinician rule;
  - 30 clips are excluded as unlabellable, declared at the freeze.

## Splits and leakage
- **Group-wise splits** by source; translations stay with their originals.
- **Duplicate checks:** exact and near-duplicate checks against the training set. Overlapping training items are dropped (`bench/sft.py`).
- **Speakers:** WazobiaSpeech test speakers (`dev`, `dev_test`) are disjoint from the training speakers.

## Intended use and limits
- **For** evaluating antenatal documentation and danger-sign detection in these three languages, and false alarms on real speech.
- **Recall:**
  - S5 and G carry recall: real speech has about 2.5% danger signs, too few to measure it;
  - **S4-W's human sample holds no danger sign, so recall on real speech is not estimable from it.**
- **Constructed and generated sets** (S5, G, R) are labelled as such in every report.
- **No patient data:** S4-W is public speech, and H is public teaching material.

## Access
- **Public sources:** WazobiaSpeech, Belebele, Ajagbe 2024.
- **Constructed sets and labels:** in this repository under `data/bench/`; S4-W labels are kept private until the labellers agree to release them.
- **Licences per source:** `docs/license-ledger.md`.
