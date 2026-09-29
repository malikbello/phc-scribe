# License and consent ledger

One row per data or model source. Nothing is used for training until its row says it may be. "Verified" means someone has read the actual license text or terms (not a summary) and recorded where.

| Source | Used for | License / terms (as understood) | Consent / ethics basis | Allowed uses | Verified |
|---|---|---|---|---|---|
| `NCAIR1/N-ATLaS` (base model) | Fine-tuning, serving | N-ATLaS Terms of Use v1.0 (Sept 2025): derivatives carry the same terms, "Powered by Awarri" suffix, 1,000 active users per rolling 30 days without a commercial license | n/a | Research and innovation; derivatives under the same terms | Gated access granted 28 Sept; terms text to be re-read and cited |
| NCAIR1 ASR models (Yoruba, Hausa, Igbo, Nigerian-accented English) | Speech recognition | N-ATLaS Terms of Use | n/a | As above | Access granted; terms to cite |
| African Medical Records (`Nigeria-Health-data-OCR-pipeline/African-Medical-Records`) @ `fa27d29` | Candidate: out-of-domain robustness slice / OCR demo (62 records; cannot be the ANC benchmark, see `docs/data-audit.md` §4) | CC BY 4.0 per card metadata and README; attribution "AMR Contributors" with the card's citation | Card says records are "synthesized/volunteer-produced"; no consent or ethics statement | Share/adapt with attribution; treat content as sensitive; no re-identification attempts | Card read 29 Sept (revision `fa27d29`); no separate LICENSE file in the repo |
| WHO ANC Digital Adaptation Kit (2021) | Schema and rule design reference | WHO publication licence (expected CC BY-NC-SA 3.0 IGO; to confirm) | n/a | Referencing and adapting data elements with attribution | No |
| Nigeria National Standing Orders (CHEWs/JCHEWs) | Rule citations | Government publication; terms to confirm | n/a | Citation | No |
| AfriMed-QA | Not used in v0 (possible regression or general eval set) | CC BY-NC-SA 4.0 | Per its paper | Non-commercial evaluation | No |
| Constructed smoke items (`tests/fixtures/smoke_items.jsonl`) | CI smoke-eval only | Written for this repo | n/a (no patient data) | Tests only; never benchmark data | Yes |
