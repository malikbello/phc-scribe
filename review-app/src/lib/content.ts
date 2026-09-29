import data from "@/data/review.json";

// Non-sensitive review content generated from the repo (scripts/export_review_data.py).

export type Concept = { id: string; label: string; danger: boolean; definition: string };
export type Rule = { id: string; name: string; when: string; message: string; severity: string };
export type Phrase = { concept: string; label: string; forms: string[] };

export const CONCEPTS: Concept[] = data.concepts;
export const RULES: Rule[] = data.rules;
export const PHRASES: Phrase[] = data.phrases;
export const QUESTIONS: string[] = data.questions;
/** Shortest evidence quote grounding accepts (serve/phc_scribe/grounding.py). */
export const MIN_QUOTE_CHARS: number = data.min_quote_chars;
export const CONCEPT_BY_ID = new Map(CONCEPTS.map((c) => [c.id, c]));
export const DANGER_IDS = new Set(CONCEPTS.filter((c) => c.danger).map((c) => c.id));

export type ReviewKind = "question" | "rule" | "concept" | "phrase";
export type ReviewRow = {
  key: string;
  kind: ReviewKind;
  title: string;
  detail: string;
  extra?: string;
  danger?: boolean;
};

export type ReviewSection = { id: ReviewKind; title: string; blurb: string; rows: ReviewRow[] };

export const REVIEW_SECTIONS: ReviewSection[] = [
  {
    id: "question",
    title: "Open questions",
    blurb: "Short answers are perfect. These decide how a few edge cases are scored.",
    rows: QUESTIONS.map((q, i) => ({ key: `question:${i + 1}`, kind: "question", title: `Question ${i + 1}`, detail: q })),
  },
  {
    id: "rule",
    title: "Danger-sign rules",
    blurb: "When each rule fires, and what the health worker is told. Present or possible fires; absent and past pregnancy do not.",
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
    blurb: "The findings we record. Is each one right, and is anything missing?",
    rows: [...CONCEPTS]
      .sort((a, b) => Number(b.danger) - Number(a.danger))
      .map((c) => ({ key: `concept:${c.id}`, kind: "concept", title: c.label, detail: c.definition, danger: c.danger })),
  },
  {
    id: "phrase",
    title: "How notes are worded",
    blurb: "Would a Nigerian PHC worker write it like this? Suggest local wordings.",
    rows: PHRASES.map((p) => ({
      key: `phrase:${p.concept}`,
      kind: "phrase",
      title: p.label,
      detail: p.forms.join(" · "),
      danger: CONCEPT_BY_ID.get(p.concept)?.danger,
    })),
  },
];

export const REVIEW_KEYS = new Set(REVIEW_SECTIONS.flatMap((s) => s.rows.map((r) => r.key)));
export const REVIEW_TOTAL = REVIEW_KEYS.size;
