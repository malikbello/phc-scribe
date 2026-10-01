import { z } from "zod";
import { CONCEPT_BY_ID, MIN_QUOTE_CHARS, REVIEW_KEYS } from "./content";

// Wire formats. Queue items and labels mirror bench/label_queue.py (QueueItem, Label)
// so exports feed scripts/build_s4_items.py unchanged.

export const Assertion = z.enum(["present", "absent", "possible", "historical"]);
export type Assertion = z.infer<typeof Assertion>;

export const SkipReason = z.enum([
  "not_pregnancy_related",
  "unintelligible",
  "not_patient_report",
  "duplicate",
  "other",
]);
export type SkipReason = z.infer<typeof SkipReason>;

// Real everyday speech (annotation guidelines §10): general health talk is a negative to be
// labelled "nothing to record", so off-topic and not-her-own-symptoms skips are not allowed.
export const SPEECH_SOURCES = new Set(["wazobia"]);
export const SPEECH_SKIP_REASONS = new Set<SkipReason>(["unintelligible", "duplicate", "other"]);
export const isSpeechSource = (source: string) => SPEECH_SOURCES.has(source);

export const Finding = z.object({
  concept: z.string().refine((c) => CONCEPT_BY_ID.has(c), "unknown concept"),
  assertion: Assertion,
  evidence: z.object({ text: z.string().min(1).max(500) }),
});
export type Finding = z.infer<typeof Finding>;

export const QueueItem = z
  .object({
    item_id: z.string().min(1).max(120),
    group_id: z.string().min(1).max(120),
    language: z.string().min(2).max(8),
    source: z.string().min(1).max(40),
    source_id: z.string().min(1).max(120),
    transcript: z.string().min(1).max(8000),
    hints: z.array(Finding.extend({ evidence: z.object({ text: z.string() }).nullable().optional() })).default([]),
  })
  .passthrough();
export type QueueItem = z.infer<typeof QueueItem>;

export const QueueUpload = z.object({
  title: z.string().min(1).max(80),
  description: z.string().max(400).optional(),
  doubleShare: z.number().min(0).max(1).default(0.2),
  showHints: z.boolean().default(false),
  /** Calibration mode: every reviewer labels every item (agreement over all pairs). */
  everyone: z.boolean().default(false),
  items: z.array(QueueItem).min(1).max(5000),
});
export type QueueUpload = z.infer<typeof QueueUpload>;

export type QueueMeta = {
  id: string;
  title: string;
  description?: string;
  createdAt: string;
  createdBy: string;
  showHints: boolean;
  order: string[];
  double: string[];
  /** Calibration mode: every reviewer labels every item. Absent on older sets. */
  everyone?: boolean;
};

export const AckStep = z.enum(["guide"]);
export type AckStep = z.infer<typeof AckStep>;

export const QueuePatch = z.object({ everyone: z.boolean() });

export const LabelInput = z
  .object({
    itemId: z.string().min(1),
    status: z.enum(["labelled", "skip"]),
    skipReason: SkipReason.optional(),
    findings: z.array(Finding).max(40).default([]),
    note: z.string().max(1000).optional(),
    elapsedMs: z.number().int().min(0).max(24 * 3600 * 1000).optional(),
  })
  .superRefine((v, ctx) => {
    if (v.status === "skip" && !v.skipReason) ctx.addIssue({ code: "custom", message: "skip needs a reason" });
    if (v.status === "skip" && v.skipReason === "other" && !v.note?.trim())
      ctx.addIssue({ code: "custom", message: "'other' needs a note" });
    const seen = new Set<string>();
    for (const f of v.findings) {
      const k = `${f.concept}|${f.assertion}`;
      if (seen.has(k)) ctx.addIssue({ code: "custom", message: `duplicate finding ${k}` });
      seen.add(k);
    }
  });
export type LabelInput = z.infer<typeof LabelInput>;

// Stored label; field names match bench/label_queue.py Label.
export type Label = {
  item_id: string;
  status: "labelled" | "skip";
  skip_reason?: SkipReason;
  findings: Finding[];
  labeller: string;
  labelled_at: string;
  note?: string;
  elapsed_ms?: number;
};

export const ReviewAnswer = z.object({
  key: z.string().refine((k) => REVIEW_KEYS.has(k), "unknown review item"),
  verdict: z.enum(["ok", "change", "answer"]),
  note: z.string().max(2000).optional(),
});
export type ReviewAnswer = z.infer<typeof ReviewAnswer>;
export type StoredReviewAnswer = ReviewAnswer & { at: string };

/** Evidence must be exact text from the transcript (after Unicode NFC normalisation). */
export function evidenceInTranscript(transcript: string, evidence: string): boolean {
  return transcript.normalize("NFC").includes(evidence.normalize("NFC"));
}

/** Length after folding (lower case, tone marks and under-dots removed), as grounding counts it. */
export function foldedLength(text: string): number {
  return text.normalize("NFD").replace(/\p{M}/gu, "").trim().length;
}

export function evidenceLongEnough(text: string): boolean {
  return foldedLength(text) >= MIN_QUOTE_CHARS;
}

export const AdjudicationInput = z
  .object({
    itemId: z.string().min(1),
    status: z.enum(["labelled", "skip"]),
    skipReason: SkipReason.optional(),
    findings: z.array(Finding).max(40).default([]),
    reason: z.string().trim().min(3, "Give a short reason").max(500),
  })
  .superRefine((v, ctx) => {
    if (v.status === "skip" && !v.skipReason) ctx.addIssue({ code: "custom", message: "skip needs a reason" });
  });
export type AdjudicationInput = z.infer<typeof AdjudicationInput>;
