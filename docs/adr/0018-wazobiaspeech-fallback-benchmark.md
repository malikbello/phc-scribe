# ADR-0018: If NigBench-MAMAI is refused, the counted benchmark is WazobiaSpeech health speech

- **Status:** Accepted by Malik, 1 Oct 2026 (with the amendment below)
- **Date:** 2026-09-30
- **Amends:** ADR-0016 §6 (the fallback only). ADR-0016's decision that the counted benchmark must be real, consented, licence-clean speech is unchanged.

## Context
- **MAMAI access is still pending.** As of 30 Sept, 17:00 UTC, `intronhealth/NigBench-MAMAI-Speech-QA` returns 403. ADR-0016 §6 says that with no access by 5 Oct, the counted benchmark becomes MamaBench (clinician-authored vignettes) plus G (generated notes). **Neither is real data.** The NAIC build requirements say validation must use "real data … not simulated or hypothetical results".
- **A real, licence-clean alternative now exists** (`docs/data-sources-survey.md`, round 5). WazobiaSpeech (EqualyzAI / Data Science Nigeria), at `Africanvoice/{yoruba,naija}_african_voices`:
  - **CC-BY-4.0 on every card.** The Yoruba card gained its licence on 30 Sept; before that it stated none.
  - Ungated. The collection is described as ethical and community-centred, with pseudonymised speaker IDs.
  - Clips are tagged by domain. Health (`HE`) is about 19% of Yoruba and 17% of Pidgin `dev_test` clips, all spontaneous speech.
  - Rough `dev_test` health pools, extrapolated from one shard each: about 1,700 Yoruba and 3,000 Pidgin clips.
  - Splits are `train`, `dev` and `dev_test`. The first shards of each share no speakers.
- **What the clips are.** Yoruba health clips are mostly first-person symptom talk ("ìrora náà pọ̀ débi pé ó ṣòro fún mi láti mí"). Pidgin health clips are more often general statements about health ("if you de schedule appointment early e go better for mama and pikin").
- **The weakness.** Pregnancy-specific clips are sparse: in the first shards, about 11% of Yoruba health clips and 17% of Pidgin health clips hit pregnancy or danger-sign terms. MAMAI is all maternal-health speech.
- **Other sources are weaker** (survey round 5):
  - AfriMed-QA consumer queries were written for made-up scenarios, so they are not real cases.
  - NaijaMed-QA has unclear provenance.
  - `med-convo-nig` has 25 recordings.

## Decision
1. **Trigger.** This ADR applies only if MAMAI access has not been granted by **5 Oct 2026** (the ADR-0016 date). If MAMAI arrives before the test-set freeze, ADR-0016 stands unchanged and WazobiaSpeech becomes a reported supplement. **Nothing switches after the freeze.**
2. **Counted benchmark (S4-W), ≥ 500 items**, drawn from WazobiaSpeech **`dev_test`** health clips (`domain == HE`) in **Yoruba and Pidgin**. Sampling uses a fixed seed and two strata per language:
   - **Enriched:** clips that match pregnancy, ANC or danger-sign terms. Matching folds away diacritics, and the term list is committed before sampling.
   - **Random:** a simple random sample of the remaining health clips.
   - Target mix: about 60% enriched and 40% random. The final numbers are recorded at the freeze.
3. **Reporting.**
   - Metrics are reported per stratum and overall.
   - **The false-alarm rate is taken from the random stratum.** That is the honest estimate of how often the system flags ordinary health talk.
   - Enrichment is disclosed in every table.
   - If fewer than 100 counted items carry at least one ANC finding, the report says that danger-sign recall is **underpowered**, and gives the CIs as measured.
4. **Task and labels.** Unchanged from ADR-0016:
   - Label the ANC vocabulary findings with assertion status and verbatim evidence.
   - Items with no ANC finding stay in.
   - Hints are shown but never pre-ticked.
   - Labelling is done in the review app, and the nurse double-labels a random 50.
5. **Input conditions.** Unchanged: (a) the human transcript; (b) the audio through N-ATLaS ASR, then the model.
6. **Training data.** WazobiaSpeech `train` health clips may be used for training, with pre-annotation disclosed. **`dev_test` never enters training.** Speaker disjointness between `train` and `dev_test` is checked on all shards before the freeze, and any shared speaker is dropped from training. `dev` is used for prompt design and the pilot.
7. **Supplements** (reported separately, not counted): G (generated notes: vitals, gestational age, rules engine), the MamaBench ANC slice, AfriMed-QA pregnancy consumer queries (labelled "prompted, not real cases"), AMR and the red-team set.
8. **Attribution.** EqualyzAI / Data Science Nigeria, CC-BY-4.0, cited in the benchmark report and the dataset card. The licence text and card revision (commit SHA) are recorded in the licence ledger at sampling time.

## Consequences
- The counted benchmark stays **real**, which is much stronger against the NAIC rule than MamaBench plus G.
- **The scope shifts again, and we say so.** The input becomes real Nigerian health speech in which ANC content is a minority. The benchmark measures (a) whether the model finds ANC findings and danger signs when they are present, and (b) whether it stays quiet on ordinary health talk. It measures little about full ANC visit histories. G still covers vitals and gestational age.
- **Statistical risk.** Fewer ANC-positive items than MAMAI would give means wider CIs on danger-sign recall (P1). Enrichment reduces this, but it cannot be removed.
- **Cost.**
  - Pull text columns only; the audio is fetched per sampled clip. The repos total about 228 GB for Yoruba alone, so nothing is downloaded in bulk.
  - Adapt `scripts/fetch_mamai.py` into a WazobiaSpeech fetcher.
  - Labelling is the same as ADR-0016: about 9–10 h for 500 items.
- **Timing.** Building the queue on 5 Oct leaves about 7 days for labelling, freezing, training and the final run. To protect that, the fetcher and queue can be built **before** 5 Oct without labelling anything, so the switch costs no time if it happens.

## Amendment at acceptance (1 Oct)
- **Test pool = `dev` + `dev_test`, not `dev_test` alone.** Counting the health clips showed `dev_test` has only 8 Yoruba and 11 Pidgin speakers (1,660 and 2,927 health clips). Adding `dev` gives 20 Yoruba and 21 Pidgin speakers (5,584 and 5,591 health clips). Neither split is used for anything else (the pilot used our own items), and `train` stays for training. Decision §2 and §6 read "`dev` + `dev_test`" from now on.
- **Statistical consequence, stated in the report:** CIs resample by speaker, so 600 clips from about 41 speakers carry far less information than 600 independent items. The report gives the number of speakers next to every S4-W result.
- **Built (nothing labelled):** `scripts/fetch_wazobia.py` (pinned revisions yo `353ea9f`, pcm `2bb5618`; text columns only), `bench/label_queue.py` (`ENRICH_TERMS`, `sample_enriched_queue`; tested). Default queue: 300 per language, 60% enriched / 40% random, seed 20261005.
