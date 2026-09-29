# NAIC 2026: which project to build

Research compiled 28 Sept 2026. Updated the same day from the full text of the official challenge page. Status: **researched and presented, not approved.** Nothing gets built until Malik explicitly approves, and the architecture doc comes before any code.

---

## 1. The challenge: what it actually requires (confirmed from the official page)

| Item | Official rule |
|---|---|
| Name | National AI Innovation Challenge (NAIC) 2026: "Build for, on, and with N-ATLAS". FMCIDE, run by ONDI + NCAIR, with Awarri Technologies |
| Deadline | **12 Oct 2026, 11:59 PM WAT. No late entries.** |
| Hard rule | Build-only. You must ship a working artefact with **genuine N-ATLAS integration**. Wrapping another general-purpose model does not qualify. Papers, decks, frameworks, mock-ups and proposals are not evaluated. |
| Validation | "Testing with actual users, real data or live benchmarks. **Not simulated or hypothetical results.**" |
| Problem statements (pick exactly one) | **PS1 Developer Infrastructure**: SDKs, playgrounds, fine-tuning kits, bilingual docs. Validation: **≥2 external beta testers**. **PS2 Voice-First Access**: "applications for Nigerians who do not type", over WhatsApp voice notes, USSD voice, IVR or low-bandwidth apps. Use cases include *primary health information*. Voice input **must use the official N-ATLAS ASR service**. Validation: **≥50 documented real user interactions**. **PS3 Sectoral Fine-Tuning**: fine-tune N-ATLAS for one clearly defined domain. Domains include ***primary healthcare and community health***. You must show **measurable improvement over base N-ATLAS** and deploy through a **documented API another developer can integrate**. The model must derive directly from N-ATLAS. Validation: **benchmark of 500+ examples vs base N-ATLAS**. |
| Tracks | **Track A Academia & Research**: at least one enrolled student or postgraduate, a faculty supervisor and an HOD letter. The lead must be at an accredited Nigerian university or research institute. **Track B Innovation & Enterprise**: a CAC certificate for companies, **or a valid ID for individual Nigerian applicants aged 18+**. Diaspora teams must be ≥50% based in Nigeria. |
| Team size | The page contradicts itself. The track cards say **2–5 members** for both tracks; the FAQ says Track B is **1–6**. Ask the organisers, or plan for at least 2 people. |
| Submission (7 items) | Working artefact, N-ATLAS integration evidence, real-world validation, technical docs (architecture, setup, usage), a 3–5 min end-to-end video, team profile, and endorsement/registration (HOD letter, or CAC/ID) |
| Judging criteria | 1) Working artefact & technical rigour, 2) N-ATLAS integration depth, 3) real-world validation, 4) impact potential, 5) **scalability & sustainability**, 6) team capability (expertise, *diversity*, delivery credibility). The build and the integration are weighted most heavily. |
| Timeline | Submit by 12 Oct. **N-ATLAS integration check 15–17 Oct.** Shortlist 16–20 Oct. **Acceleration and mentorship 25 Oct–4 Nov**, with N-ATLAS API credentials and compute credits for shortlisted teams. **Finals at the Digital Nigeria Showcase, 8–10 Nov.** |
| What you win | **Track B:** government procurement pathway review, ONDI incubation, investor introductions, N-ATLAS API integration support, national AI startup directory. **Track A:** NCAIR research-lab partnership, N-ATLAS co-contributor credit, FG recognition, publication support. **All shortlisted teams:** summit invite, NITDA talent registry, priority for government AI pilots. No cash prize. |

**What this means:** the real prize is a government pilot and procurement pathway (Track B). That favours a product government is the natural buyer for. The 12 Oct submission is a first gate: shortlisted teams get about 3 more weeks, plus compute, to harden the build before finals.

### What changed after reading the official page
1. **Eligibility is no longer a blocker.** Track B accepts individuals with a valid ID, so no CAC registration is needed. The only open point is team size (2–5 vs 1–6).
2. **PS3 is now the better route for the health idea.** "Primary healthcare and community health" is a named PS3 domain. PS3 is validated with a 500+ example benchmark against base N-ATLAS, **not** 50 field interactions, so it doesn't depend on getting clinic access within 10 days. PS3 also has no "official ASR service" constraint, which PS2 has and which conflicts with running offline on our own box.
3. **PS2's target user is the citizen who doesn't type**, not the health worker. A health-worker tool is a weak fit for PS2.
4. **"Not simulated" matters.** CHEWs working through made-up vignettes (the earlier PS2 plan) could be judged simulated. A PS3 benchmark must be built from **real data**.
5. **Field testing moves to the acceleration phase** (25 Oct–4 Nov), after shortlisting, which is where it realistically fits.

### Competitors already visible (public repos)
- **N-ATLAS Kit** (PS1): polished SDKs (npm + PyPI), a GPU self-hosting gateway, a playground and docs in English and Hausa. It is strong. Entering PS1 head-on against it is a bad bet.
- **AgroVoice** (PS2): voice agricultural advice for maize and tomato, with safety routing. Agriculture voice advice is already taken in this challenge.
- **ClinicBridge**: an MIT thesis prototype for health-worker↔patient translation in Nigerian PHCs. It needs internet, uses Google Cloud ASR rather than N-ATLAS, and is not certified.

---

## 2. The model we must build on: N-ATLaS, strengths and traps

- **What it is:** a Llama-3 8B fine-tune trained on about 392M tokens of Hausa, Yoruba, Igbo and English. It ships with 4 Whisper-Small (244M) ASR models, one per language plus Nigerian-accented English. The ASR takes a hard 30-second window of 16 kHz mono audio, so longer audio must be chunked.
- **Quality, from an independent AfroBench-LITE eval:** Hausa 28.9→44.1, Yoruba 24.4→38.4, Igbo 27.7→38.7, English 54.8→62.8 compared with base Llama-3-8B-Instruct. That is a real improvement, but **still weak in absolute terms**. It must not be trusted to make clinical, legal or financial judgements on its own.
- **Access:** the Hugging Face repos are gated, and the weights are 16 GB. There is no public hosted API. An official API does exist, though: shortlisted teams receive N-ATLAS API credentials.
- **Edge feasibility:** an 8B model at Q4 is about 5 GB and runs on CPU. The reported speeds need our own benchmark. Llama-class 8B Q4 runs at about 6–9 tok/s on an Intel N100/N150 mini-PC with 16 GB, and about 14 tok/s on a Jetson Orin Nano Super. Whisper-Small runs below real time on a Raspberry Pi 5 and faster on x86. **An offline box that runs the whole N-ATLaS stack for one clinic or one community is realistic.**

### ⚠️ The license trap, the most important finding in this document
N-ATLaS uses Awarri's "Open-Source Research and Innovation License" (Terms of Use v1.0, Sept 2025). It is **not** OSI open source. Its terms:
- **A cap of 1,000 active end-users per rolling 30 days.** An active end-user is "an individual who directly interacts with N-ATLaS outputs". Beyond that you need a commercial license from Awarri and FMCIDE.
- **Not for enterprise or commercial deployment** without a separate agreement. Research, education, civic tech, accessibility, cultural preservation and community projects are allowed.
- **Share-alike on derivatives.** A fine-tune stays under these terms.
- Attribution is mandatory. Renamed derivatives must say "Powered by Awarri". Surveillance, profiling, disinformation and military use are prohibited.

**Consequence:** "scale to all of Nigeria" and "raise money" cannot rest on N-ATLaS under its free terms. Any serious plan needs:
1. a design where end-users are few and professional (for example health workers, not the public),
2. a model-agnostic architecture, so N-ATLaS is one swappable engine, and
3. either a commercial license from Awarri at scale (the challenge's procurement pathway is the natural route to one) or our own models later.

Consumer apps (farmers, students, bank customers) hit the cap almost immediately.

---

## 3. The problems, with real numbers

### Health: Nigeria carries a global share of the burden
- **Maternal deaths:** about 75,000 in 2023, which is **28.7% of all maternal deaths on Earth**. Nigeria ranks #1 globally, with a ratio of 993 per 100k live births (WHO/UNICEF/UNFPA/World Bank, *Trends in Maternal Mortality 2000–2023*).
- **Newborns and children:** neonatal mortality is 41/1,000, essentially flat since 2018. Under-5 mortality is 102/1,000. Only **46%** of births have a skilled attendant, and ANC coverage is 63%. The North West is worst: Kano's neonatal rate is 59 and Jigawa's under-5 rate is 161 (NDHS 2023–24).
- **Malaria:** Nigeria has **24.3% of global cases and 30.3% of global deaths**, about 68.5M cases and about 184,800 deaths in 2024 (World Malaria Report 2025).
- **Workforce collapse:** about 55,000 licensed doctors serve 220M+ people, roughly 1 doctor per 9,000+ against WHO's 1:600, and about 15,000 doctors left in 5 years (NMA 2025). Skilled health-worker density is 1.95 per 1,000. Community health workers (CHOs, CHEWs, JCHEWs) carry primary care under the **National Standing Orders**, the national protocol book (new edition Sept 2024).
- **PHC system:** the government committed to revitalise **17,600 PHCs (one per ward)**. Only **1,295 (7.3%)** were done by Sept 2025. 8,000+ PHCs get quarterly direct financing through the BHCPF. The World Bank **HOPE-PHC** program became effective in Sept 2025 and is focused on *quality of services*.
- **Paperwork burden:** a 5-country PHC study that included Nigeria found recording takes **about one-third of consultation time**, **about 9 hours a month per worker** go on monthly reports, and there are **about 35 monthly reporting forms**. DHIS2 has been the national health management information system (NHMIS) since 2013 and is in all states since 2021. The data is still collected on paper registers and totalled by hand each month.
- **Infrastructure:** **85–87M Nigerians have no electricity**, the world's largest deficit. About **140M** live under mobile broadband coverage but don't use mobile internet (GSMA 2025).

### Agriculture
- 1 extension officer per **6,446 farming households** (2024), against a recommended 1 per 800–1,000. About **50% post-harvest loss** on fresh produce (USAID 2024).
- The field is crowded: AgroVoice is already in NAIC, there is an FG and IFAD "AI-enabled extension" push, and many funded agritechs. Farmers as end-users hit the 1,000 cap fast.

### Education
- **18.3M out-of-school children** (UNICEF 2024).
- **Policy risk:** on 12 Nov 2025 the FG **scrapped mother-tongue instruction** and made English the sole medium. A local-language tutor now runs against federal policy. Children as end-users also hit the cap.

### Legal services
- **80,812 inmates, 51,955 (64%) awaiting trial** (NCoS, Feb 2026). The Legal Aid Council handled only **7,140 cases in 2024**.
- The gap is large and the use is civic, which the license allows. But there is little budget, and getting ≥50 real interactions with detainees or paralegals in 14 days is unrealistic.

### Financial inclusion
- E-payment fraud losses were **₦25.85bn in 2025**, down 51% from 2024 (NIBSS). That is real, but small next to the problems above.
- The buyers are banks, which is commercial use and blocked by the license. Least suitable here, even though it's closest to Malik's day job.

---

## 4. Candidates scored

Weights: problem severity 20, edge/offline fit 15, challenge fit (N-ATLAS depth + validation reachable in 14 days) 20, license survives scale 10, fundability 15, differentiation 10, 14-day feasibility 10. Each is scored 1–5 and the total is scaled to 100.

These are re-scored after reading the official page. PS3's benchmark-based validation raised "Fit" for every idea that maps to a PS3 domain (A, B, C, E), and PS1's 2-beta-tester rule raised G.

| # | Candidate | Best PS | Sev | Edge | Fit | Lic | Fund | Diff | Feas | **Score** |
|---|---|---|---|---|---|---|---|---|---|---|
| **A** | **Offline voice copilot for PHC frontline workers** (maternal/newborn + fever), a solar edge box per facility | **PS3** | 5 | 5 | 5 | 4 | 4 | 4 | 3 | **89** |
| B | Drug-shop (PPMV) test-and-treat assistant for malaria/fever | PS3 | 5 | 4 | 4 | 2 | 4 | 4 | 3 | 78 |
| C | Legal-rights / bail-triage assistant for awaiting-trial detainees and paralegals | PS3 | 4 | 4 | 4 | 5 | 2 | 5 | 3 | 76 |
| G | "N-ATLAS Edge": a quantized N-ATLaS + ASR runtime for CPU/ARM with measured quality loss | PS1 | 3 | 5 | 5 | 4 | 2 | 3 | 4 | 75 |
| E | Offline learning tutor for out-of-school children | PS3 | 5 | 5 | 4 | 2 | 2 | 3 | 3 | 73 |
| D | Voice agricultural extension | PS2 | 4 | 3 | 4 | 2 | 4 | 1 | 4 | 67 |
| F | Voice banking / scam shield for low-literacy users | PS2 | 3 | 2 | 3 | 1 | 4 | 3 | 4 | 58 |

Why B isn't first despite the huge reach: PPMVs (patent and proprietary medicine vendors, the local drug shops) are the first stop for 75% of rural Nigerians and treat 55% of under-5 fevers. But they are businesses, which puts them in the license's commercial zone, and pharmacy regulation adds friction. **B is the natural phase-2 expansion of A.**

G is not a standalone company, but it is **the foundation layer A needs anyway** (the quantized, offline deployment of the fine-tuned model). It is also the evidence for A's "scalability & sustainability" score.

---

## 5. Recommendation: A, entered under PS3, deployed with G

**An offline, voice-first clinical copilot for frontline primary-care workers, running on one low-cost solar-powered edge box per PHC.** Working name TBD.

### What we submit to NAIC (PS3: Sectoral Fine-Tuning, primary healthcare and community health)
The product below is the vision. The NAIC entry is its core, built so it meets every PS3 rule:
1. **A community-health fine-tune of N-ATLaS** (QLoRA on N-ATLaS itself, so it derives directly from it). It is trained for two jobs where base N-ATLaS is likely weak: (a) turning a spoken or written PHC visit in Hausa, Yoruba, Igbo, English or a mix into a **structured encounter record**, and (b) **answering primary-care questions grounded in Nigerian protocols** (National Standing Orders, and WHO ANC and IMCI rules).
2. **A benchmark of 500+ real-data examples against base N-ATLaS.** The leading candidate source is **AfriMed-QA**, a real pan-African medical QA set of 15k+ questions, **over half of its expert questions from Nigeria**, with consumer health queries included. It is CC BY-NC-SA 4.0, which is fine for evaluation. We would filter it to primary-care, maternal, child and infectious-disease topics. A possible second source for the extraction task is the **African Medical Records** dataset of handwritten Nigerian clinical records (consent and terms to be verified). The final benchmark design is decided in the architecture doc.
3. **A documented API** (OpenAI-compatible) that another developer can integrate, plus **an offline edge deployment** of the same model, quantized, running on a mini-PC with the official N-ATLaS ASR weights. The edge deployment is our answer to "scalability & sustainability".
4. **Field pilot with CHEWs during the acceleration phase** (25 Oct–4 Nov) if shortlisted, as extra evidence for the finals.

**Why PS3 over PS2:** "Primary healthcare and community health" is a named PS3 domain. Validation is a real-data benchmark instead of 50 field interactions arranged in 10 days. There is no requirement to use the hosted ASR service, which would conflict with running offline. And it plays to data-science strengths: fine-tuning, evaluation and benchmarks.

**Compute:** QLoRA fine-tuning of an 8B model fits on a free Kaggle or Colab T4 GPU, or a few hours of rented A100 time (roughly tens of dollars). Shortlisted teams also get compute credits. Inference and the edge deployment run on CPU.

### The job it does
The CHEW or midwife talks through the visit in Hausa, Yoruba, Igbo, Nigerian English or a mix. The box, with no internet:
1. **Transcribes** the visit with the official N-ATLaS ASR, running locally.
2. **Extracts** a structured encounter using N-ATLaS: symptoms, vitals, gestational age, danger signs and so on. Output is constrained to a JSON schema, so the model fills fields and does not free-write advice.
3. **Runs a deterministic protocol engine** built from the National Standing Orders plus WHO ANC and IMCI rules. **Rules decide the danger signs and referral, not the LLM.** Every flag cites the protocol line it came from.
4. **Writes the paperwork automatically:** the register entry, a referral note in English for the receiving hospital, and the monthly NHMIS/DHIS2 summary. The worker gets back part of that third of consultation time and the 9 hours a month.
5. **Syncs** when any connectivity appears (a phone hotspot, or a weekly trip to town).

### Why this wins on every axis we care about
- **A real problem, measured at world scale:** Nigeria is #1 globally for maternal deaths and malaria deaths. It is a global problem centred in Nigeria.
- **Edge is the requirement, not a gimmick:** 85M+ people have no power and PHCs are offline. Cloud tools (ClinicBridge, Intron, AISHA) cannot serve these sites.
- **Deep N-ATLaS integration:** a fine-tuned N-ATLaS derivative with a measured improvement over base, the official ASR weights for voice capture, and an offline runtime for both. That is exactly what the judges are told to reward.
- **Survives the license:** the end-users are health workers, 2–5 per PHC, so 1,000 users covers roughly 200–500 facilities. That is a full state pilot inside the free terms. Public primary care counts as civic use. Scaling beyond that goes through an Awarri commercial license, which the government procurement pathway exists to unlock. The architecture stays model-agnostic as insurance.
- **Safe by construction:** MAM-AI (Zanzibar, 2026) found that a small on-device model "cannot be both helpful and safe" as a clinical generator. Our design never asks it to be. Penda Health (Kenya, 39,849 visits) showed an AI safety net cut diagnostic errors 16% and treatment errors 13%, which is evidence the safety-net pattern works.
- **Data protection:** health data is sensitive under Nigeria's NDPA 2023. Processing on the box keeps it in the facility, and that is easy to explain to regulators.
- **A buyer exists and is funded:** state PHC boards and NPHCDA (17,600-PHC target, BHCPF), the World Bank HOPE-PHC (quality of services), and donors (Gates, Global Fund, UNICEF, Gavi). The NAIC prize itself (priority pilots, procurement review) matches this.

### Why it's fundable, the venture story (to be tested, not assumed)
The wedge is the PHC visit. Once every facility is a live, structured data node, it expands into:
1. **Automatic NHMIS reporting** with better data quality, which government and donors pay for.
2. **Verification of BHCPF and insurance (NHIA) services**, meaning payments tied to services that were actually delivered.
3. **Drug and commodity forecasting** from real consumption.
4. **Aggregated epidemic early-warning** signals for NCDC. This is aggregate public-health reporting, not people surveillance, which the license bans. Wording matters.
5. **PPMVs (phase 2)** and **cross-border expansion**. Hausa and Yoruba cross borders (Niger, Ghana, Benin), and the same design fits Ghana's CHPS clinics.

The moat is the consented Nigerian-language clinical speech and encounter dataset, a protocol engine validated with CHPRBN and NPHCDA, installed hardware, and government integrations.

**Honest caveats:** B2G sales cycles are slow, and donors usually fund pilots before governments buy. This is a durable impact company with a platform upside. It is not a quick consumer rocket.

### Competition, and the gap we fill
| Player | What it is | Why it doesn't cover our wedge |
|---|---|---|
| CHPRBN National Standing Orders app (Zijela ICT) | Official digital reference of the standing orders | A reference book. No voice, local-language capture, documentation or safety net (confirm features) |
| THINKMD (Kano study) | IMCI decision support for CHWs | Form-driven, not voice or Nigerian languages, not N-ATLaS |
| ClinicBridge | Worker↔patient translation app | Needs internet, uses Google ASR, only translates |
| Intron Health ($1.6M pre-seed) | Clinical speech recognition in 30 hospitals | Hospital and cloud based, not an offline PHC tool |
| AISHA | Patient-facing health chatbot on WhatsApp | Consumer-facing and online |
| kSanté (Pleias, Senegal) / MAM-AI (Zanzibar) | Offline clinical Q&A on phones | Not Nigeria or its languages, and Q&A only (no documentation or protocol engine). They prove the tech works. |

**Nobody combines offline operation, Nigerian-language voice, a protocol-bound safety net, automatic register/NHMIS output and N-ATLaS.** That combination is the product.

---

### Competition check: who else is likely in health (28 Sept 2026)
NAIC submissions are private, so this only covers public repos, papers and announcements. Silence doesn't mean nobody else is there.

| Who | What | How much they collide with us |
|---|---|---|
| **HelpMum** (Nigerian maternal-health social enterprise with government ties) | **MamaBot-Llama**: Llama-3.1-8B LoRA-tuned on **36,000+ maternal Q&A pairs**. **Vax-Llama**: 9,000 vaccination Q&A pairs. English↔Hausa/Yoruba/Igbo translator models. A paper on it appeared Aug 2026 (arXiv 2609.22110). | **High for any "maternal health Q&A" fine-tune.** They are one retrain away from a PS3 entry with a data head start we can't match in 14 days. It is patient-facing. |
| The obvious idea | "A health chatbot that advises patients in Hausa" is literally the example used in N-ATLaS launch coverage | Expect many PS2 and PS3 entries doing patient Q&A |
| **Ìtọ́jú** (equalyz.ai) | "AI Maternal & Child Health Companion", 24/7 maternal and child health information in Nigeria | Medium. Another patient-facing maternal AI, which confirms that lane is crowded. |
| ClinicBridge | Worker↔patient translation for PHCs | Low. Needs internet, uses Google ASR, only translates |
| AISHA | WhatsApp patient health assistant | Low. Patient-facing and online |
| Hausa medical ASR research (MMS-based) | Better decoding for Hausa medical speech | Low. Research, not N-ATLaS |
| Previous Awarri N-ATLaS challenge (2025) | Winners: Civic Access (legal), Farm Eyes (agriculture), Lauya mi (tenant rights) | No health winner. **Legal is already a proven lane**, which weakens candidate C. |

**Nobody found is doing structured clinical documentation** (visit → register/NHMIS record) in Nigerian languages, for health workers, offline, on N-ATLaS.

**Adjustment:** **drop maternal/health Q&A as the fine-tune target.** Make the PS3 model a **clinical documentation model**: spoken or written visit notes in Nigerian languages in, structured, protocol-checkable records out. The protocol engine stays rule-based, outside the model. The pitch becomes "the AI scribe and safety net for the PHC worker", not another health chatbot.

## 6. Risks and how we de-risk them before building

| Risk | Severity | Mitigation / go-no-go test |
|---|---|---|
| **Team size**: the track cards say 2–5, the FAQ says Track B is 1–6 | Medium | Email the organisers now. Meanwhile, line up at least one teammate: a clinician or CHEW, or a native-speaker reviewer, which also helps the "team diversity" criterion. |
| Eligibility | Resolved | Track B accepts an individual with a valid ID; no CAC needed |
| **Fine-tune doesn't beat base N-ATLaS by a clear margin** | High | **Day-1–2 gate:** run base N-ATLaS on a pilot slice of the benchmark first, and pick tasks where it is measurably weak. Structured extraction and Nigerian protocol specifics are the likely gaps. |
| **"Not simulated" rule**: the benchmark must be real data | High | Build it from real sources (AfriMed-QA, real clinical records). Keep any synthetic or augmented data out of the test set, and say so plainly in the docs. |
| **Training data terms**: NC-SA datasets, WHO guidelines (CC BY-NC-SA IGO), National Standing Orders terms, and whether outputs from other models may be used for training | Medium | Decide in the architecture doc. Keep a license ledger per source, and never train on the test split. |
| Translation quality of Nigerian-language benchmark items | Medium | Native-speaker review for each language used. Start with English + one Nigerian language if review capacity is thin. |
| GPU access for fine-tuning | Low | Free Kaggle/Colab T4 with QLoRA, or a few hours of rented A100 |
| ASR too weak on clinical speech, noisy clinics or code-switching | Medium (for the edge product; not needed for the PS3 benchmark) | Measure WER on real recordings during the acceleration-phase pilot, and narrow the languages if needed |
| License at scale | Medium | Health workers as the end-users, a model-agnostic adapter, and an Awarri commercial license through the procurement pathway. The fine-tune is itself an N-ATLaS derivative: same terms, and it must carry "Powered by Awarri". |
| Clinical safety / regulation | High | No diagnosis claims. Rules decide, the worker confirms, and every flag is cited. "Decision support, not a medical device". Seek CHPRBN/NPHCDA endorsement. |
| Scope creep in 14 days | High | **One domain slice only for NAIC:** antenatal care and danger signs, plus the encounter-extraction task. Fever/IMCI and PPMVs come after. |

---

## 7. What happens next (with approval gates)

1. **Malik decides:** approve A under PS3 (or pick another), confirm Track B as an individual, settle the team-size question, and choose the first Nigerian language to benchmark.
2. **Gate 0 (days 1–2):** request N-ATLaS gated access on Hugging Face today (approval can take time). Check the AfriMed-QA and African Medical Records terms. Run base N-ATLaS on a pilot benchmark slice to confirm there is room to improve.
3. **Architecture and scale doc**: fine-tune recipe, benchmark design, data license ledger, API, edge hardware, power and sync, the protocol engine, and the national scale path. **Malik approves it before any code is written.**
4. Build, fine-tune, benchmark, then write the docs and video, and submit before 12 Oct.
5. If shortlisted: harden the build and run the CHEW field pilot (25 Oct–4 Nov), then the finals (8–10 Nov).

---

## Sources
- NAIC 2026 official page (full text supplied by Malik, 28 Sept 2026): https://ncair.nitda.gov.ng/naic/
- AfriMed-QA: https://github.com/intron-innovation/AfriMed-QA, https://arxiv.org/abs/2411.15640
- African Medical Records dataset: https://huggingface.co/datasets/Nigeria-Health-data-OCR-pipeline/African-Medical-Records
- Eligibility and tracks (summaries): https://edutorial.ng/call-for-applications-nitda-national-ai-innovation-challenge-2026/, https://www.scholarshipregion.com/nitda-national-ai-innovation-challenge/
- N-ATLAS Kit (PS1 entrant; license and model details): https://github.com/Kambah123/N-ATLAS-Kit
- AgroVoice (PS2 entrant; quotes the PS2 and PS3 rules): https://github.com/mubayyingcc-AI/agrovoice-natlas
- ClinicBridge: https://github.com/IgweEmmanuel/clinicbridge-releases
- N-ATLaS model card and terms: https://huggingface.co/NCAIR1/N-ATLaS; TechCabal on the terms: https://techcabal.com/2025/09/25/nigerian-government-awarri-launch-n-atlas/
- Independent N-ATLaS eval (AfroBench): https://huggingface.co/blog/seun-ajayi/n-atlas-evaluation-report
- Maternal mortality 2000–2023: https://www.unfpa.org/publications/trends-maternal-mortality-2000-2023
- NDHS 2023–24 Key Indicators: https://dhsprogram.com/pubs/pdf/PR157/PR157.pdf
- World Malaria Report 2025: https://cdn.who.int/media/docs/default-source/malaria/world-malaria-reports/world-malaria-report-2025-executive-summary-eng.pdf
- NMA doctor ratio: https://thenigerialawyer.com/nma-raises-alarm-nigerias-doctor-patient-ratio-soars-to-18000-as-emigration-continues/
- PHC revitalisation progress: https://nigeriahealthwatch.com/articles/thought-leadership/nigerias-phc-revitalisation-ambition-reality-and-the-urgency-for-accountability/
- HOPE-PHC: https://documents.worldbank.org/en/publication/documents-reports/documentdetail/099090924142029907
- National Standing Orders: https://chprbn.gov.ng/standingorders/; NSO app: https://play.google.com/store/apps/details?id=com.zijela.chprbn
- PHC recording and reporting burden: https://pubmed.ncbi.nlm.nih.gov/34511083/
- DHIS2 and NDHI: https://www.digitalhealth.gov.ng/
- PPMVs: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6437880/
- Penda Health AI Consult: https://arxiv.org/abs/2507.16947
- MAM-AI (Zanzibar): https://arxiv.org/abs/2606.29580
- kSanté (Pleias): https://pleias.ai/blog/blogbuilding-offline-first-ai-for-community-health-workers-in-west-africa
- Intron Health: https://businessday.ng/health/article/nigerian-health-startup-secures-1-6m-for-clinical-speech-conversion/
- Electricity access: https://trackingsdg7.esmap.org/sites/default/files/download-documents/chapter1_accesstoelectricity.pdf
- GSMA usage gap: https://nairametrics.com/2026/09/16/gsma-warns-rising-smartphone-costs-could-deepen-nigerias-mobile-internet-gap/
- Extension ratio: https://africasustainabilitymatters.com/nigerias-digital-agriculture-push-aims-to-transform-extension-services-for-millions-of-smallholder-farmers/
- Post-harvest loss: https://nairametrics.com/2024/04/21/post-harvest-losses-for-fresh-produce-at-almost-50-in-nigeria-usaid/
- Out-of-school children: https://www.unicef.org/nigeria/press-releases/nigerias-children-crossroads-new-report-shows-progress-millions-still-left-behind
- Mother-tongue policy scrapped: https://www.thecable.ng/fg-adopts-english-for-child-education-scraps-mother-tongue-policy/
- Awaiting-trial inmates: https://www.thecable.ng/ncos-51955-out-of-80812-inmates-in-nigerias-prisons-are-awaiting-trial/
- NIBSS fraud 2025: https://nibss-plc.com.ng/digital-payment-fraud-drops-51-to-n25-85b-lagos-accounts-for-63/
- Edge benchmarks: https://www.starryhope.com/ai/best-mini-pcs-local-llms-2026/, https://proventusnova.com/blog/llm-inference-jetson-orin-llamacpp-ollama
