import data from "@/data/review.json";

// Non-sensitive review content generated from the repo (scripts/export_review_data.py).

export type Concept = { id: string; label: string; danger: boolean; definition: string };
export type Rule = { id: string; name: string; when: string; message: string; severity: string };
export type Phrase = { concept: string; label: string; forms: string[] };
export type Medication = { id: string; label: string; definition: string };

export const CONCEPTS: Concept[] = data.concepts;
export const RULES: Rule[] = data.rules;
export const PHRASES: Phrase[] = data.phrases;
export const QUESTIONS: string[] = data.questions;
export const MEDICATIONS: Medication[] = data.medications;
/** Shortest evidence quote grounding accepts (serve/phc_scribe/grounding.py). */
export const MIN_QUOTE_CHARS: number = data.min_quote_chars;
export const CONCEPT_BY_ID = new Map(CONCEPTS.map((c) => [c.id, c]));
export const DANGER_IDS = new Set(CONCEPTS.filter((c) => c.danger).map((c) => c.id));
export const DANGER_LABELS = CONCEPTS.filter((c) => c.danger).map((c) => c.label);


// Plain-language framing for each open question in docs/annotation-guidelines.md §9:
// what it is about, what the app does today, and the question itself. Keyed by the
// question number; a test checks every question has an entry.
export type QuestionContext = { about: string[]; today: string; ask: string };
export const QUESTION_CONTEXT: Record<number, QuestionContext> = {
  1: {
    about: ["Findings list", "DS-001 to DS-014"],
    today: "We treat the 14 signs below as danger signs. Each one fires a referral rule.",
    ask: "Is this list right for Nigerian primary care? Should we add, merge or remove any?",
  },
  2: {
    about: ["DS-003 Severe headache", "CB-001 Possible pre-eclampsia", "VS-002 Hypertension"],
    today: "Only a headache described as severe counts as a danger sign. A plain \"headache\" with BP 140/90 or higher raises the high-BP flag, but not the pre-eclampsia flag.",
    ask: "Should any headache plus BP of 140/90 or above count as a possible pre-eclampsia sign, even if it isn't called severe?",
  },
  3: {
    about: ["VS-001 Severe hypertension", "VS-002 Hypertension"],
    today: "Some notes write 140/90 as \"14/9\". Our labelling guidelines treat \"BP 14/9\" as 140/90.",
    ask: "Is that shorthand common and safe enough to read that way, or should those notes go to a person to check?",
  },
  4: {
    about: ["VS-001 Severe hypertension", "VS-002 Hypertension"],
    today: "If a note gives only one BP number (e.g. \"systolic 150\"), our guidelines record no BP at all, so the BP rules can't fire.",
    ask: "Should we record a single number, and let a high systolic alone trigger the BP flags?",
  },
  5: {
    about: ["LB-001 Severe anaemia"],
    today: "The severe-anaemia rule fires when Hb is below 7 g/dL, or PCV is below 21% (because many PHCs measure PCV, not Hb).",
    ask: "Is PCV below 21% the right equivalent of Hb below 7 g/dL?",
  },
  6: {
    about: ["All danger-sign rules"],
    today: "13 rules cite WHO antenatal guidance and 5 point to the National Standing Orders, but the edition and sections aren't confirmed, and no citation has been checked yet.",
    ask: "Which edition and sections of the National Standing Orders for CHEWs/JCHEWs should each rule cite? (A rough pointer is fine.)",
  },
  7: {
    about: ["Findings list", "How notes are worded"],
    today: "We recognise the English wordings in \"How notes are worded\", plus draft Yoruba forms.",
    ask: "What words do women or health workers commonly use for these signs, in English, Pidgin or Yoruba, that we might miss?",
  },
};

export type ReviewKind = "question" | "rule" | "concept" | "phrase" | "medicine";
export type ReviewRow = {
  key: string;
  kind: ReviewKind;
  title: string;
  detail: string;
  extra?: string;
  /** Reference list shown under the card (e.g. the danger signs a question refers to). */
  list?: { title: string; items: string[] };
  /** For questions: what it is about and what the app does today. */
  context?: QuestionContext;
  danger?: boolean;
};

export type ReviewSection = { id: ReviewKind; title: string; blurb: string; rows: ReviewRow[] };

const QUESTION_SECTION: ReviewSection = {
  id: "question",
  title: "Open questions",
  blurb: "Seven edge cases about the rules and findings you just reviewed. Each card says what it's about and what the app does today. A short answer is perfect.",
  rows: QUESTIONS.map((q, i) => {
    const context = QUESTION_CONTEXT[i + 1];
    return {
      key: `question:${i + 1}`,
      kind: "question" as const,
      title: `Question ${i + 1}`,
      detail: context?.ask ?? q,
      context,
      ...(/danger-sign list|these signs/i.test(q)
        ? { list: { title: `The ${DANGER_LABELS.length} danger signs we use now`, items: DANGER_LABELS } }
        : {}),
    };
  }),
};

// The pharmacist's step: one card per medication class in the record schema, then two
// open questions. Answers export with the rest of the sign-off.
const MEDICINE_QUESTIONS = [
  {
    key: "medicine-q:local-names",
    title: "Local and brand names",
    ask: "What names do women and health workers use for these medicines? Brand names, Pidgin, Yoruba, or how people describe them (\"blood tonic\", \"malaria drug\", \"injection for belle\"). Please say which medicine each name belongs to.",
  },
  {
    key: "medicine-q:missing",
    title: "Anything missing?",
    ask: "Is any medicine routinely given at antenatal visits in Nigerian primary health care missing from this list?",
  },
];

const MEDICINE_SECTION: ReviewSection = {
  id: "medicine",
  title: "Medicines",
  blurb: "The medicines the app records at an antenatal visit. Is each one described correctly for Nigerian PHC? Then add the names people actually use.",
  rows: [
    ...MEDICATIONS.map((m) => ({ key: `medicine:${m.id}`, kind: "medicine" as const, title: m.label, detail: m.definition })),
    ...MEDICINE_QUESTIONS.map((q) => ({ key: q.key, kind: "question" as const, title: q.title, detail: q.ask })),
  ],
};

// Order matters: reviewers first confirm the rules and the findings they use, then
// answer the edge-case questions about them, then check note wording, then medicines.
export const REVIEW_SECTIONS: ReviewSection[] = [
  {
    id: "rule",
    title: "Danger-sign rules",
    blurb: "Step 1. When the app raises a danger flag, and what the health worker is told. Present or possible fires; absent and past pregnancy do not.",
    rows: RULES.map((r) => ({
      key: `rule:${r.id}`,
      kind: "rule",
      title: `${r.id} · ${r.name}`,
      detail: r.when,
      extra: r.message,
      danger: true,
    })),
  },
  {
    id: "concept",
    title: "Findings list",
    blurb: "Step 2. Every symptom the app records, with its definition. The rules above are built from these. Danger signs are marked red.",
    rows: [...CONCEPTS]
      .sort((a, b) => Number(b.danger) - Number(a.danger))
      .map((c) => ({ key: `concept:${c.id}`, kind: "concept", title: c.label, detail: c.definition, danger: c.danger })),
  },
  QUESTION_SECTION,
  {
    id: "phrase",
    title: "How notes are worded",
    blurb: "Step 4. Wordings used in the practice notes. Would a Nigerian PHC worker write it like this? Suggest local wordings.",
    rows: PHRASES.map((p) => ({
      key: `phrase:${p.concept}`,
      kind: "phrase",
      title: p.label,
      detail: p.forms.join(" · "),
      danger: CONCEPT_BY_ID.get(p.concept)?.danger,
    })),
  },
  MEDICINE_SECTION,
];

export const REVIEW_KEYS = new Set(REVIEW_SECTIONS.flatMap((s) => s.rows.map((r) => r.key)));
export const REVIEW_TOTAL = REVIEW_KEYS.size;

export type Role = "admin" | "clinician" | "pharmacist" | "annotator";

/** The sign-off steps a role works through. Annotators have none. */
export function sectionsFor(role: Role): ReviewSection[] {
  if (role === "annotator") return [];
  if (role === "pharmacist") return [MEDICINE_SECTION];
  return REVIEW_SECTIONS;
}

export function reviewKeysFor(role: Role): Set<string> {
  return new Set(sectionsFor(role).flatMap((s) => s.rows.map((r) => r.key)));
}
