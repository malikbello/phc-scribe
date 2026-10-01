import { DANGER_IDS } from "./content";
import type { Finding, Label, SkipReason } from "./schema";

// Gold-label resolution (annotation guidelines §10.8). Only disagreements that need clinical
// judgement reach a person; everything else resolves by rule, and the rule is recorded:
//   single       one label
//   agreed       every label gives the same answer (same findings + assertions, or all skip)
//   majority     >= 3 labels, a strict majority agree, and no minority label differs from it
//                on any danger sign (present/possible): a danger-sign split always goes to
//                the clinician, however many outvote it
//   adjudicated  the clinician's decision (always wins; reopens if the labels change after)
// Evidence spans may differ between agreeing labels; the gold copy comes from the first
// agreeing labeller by id, so the result is deterministic.

export type Resolution = "single" | "agreed" | "majority" | "adjudicated";

export type Adjudication = {
  item_id: string;
  status: "labelled" | "skip";
  skip_reason?: SkipReason;
  findings: Finding[];
  reason: string;
  adjudicator: string;
  adjudicated_at: string;
  /** The labels the decision was made on; if they change, the item needs a fresh look. */
  basis: string;
};

export type Resolved =
  | { state: "unlabelled" }
  | { state: "pending"; why: string }
  | { state: "resolved"; resolution: Resolution; gold: Label; stale?: false };

const POSITIVE = new Set(["present", "possible"]);

export function answerKey(l: Pick<Label, "status" | "findings">): string {
  if (l.status === "skip") return "skip";
  return [...new Set(l.findings.map((f) => `${f.concept}|${f.assertion}`))].sort().join(",") || "nothing";
}

function dangerKey(l: Pick<Label, "status" | "findings">): string {
  if (l.status === "skip") return "";
  return [...new Set(l.findings.filter((f) => DANGER_IDS.has(f.concept) && POSITIVE.has(f.assertion)).map((f) => f.concept))].sort().join(",");
}

/** Fingerprint of the labels an adjudication was based on. */
export function basisOf(labels: Label[]): string {
  return labels.map((l) => `${l.labeller}=${answerKey(l)}`).sort().join(";");
}

function goldFrom(l: Label, resolution: Resolution): Label {
  return {
    item_id: l.item_id,
    status: l.status,
    ...(l.skip_reason ? { skip_reason: l.skip_reason } : {}),
    findings: l.status === "skip" ? [] : l.findings,
    labeller: `gold:${resolution}`,
    labelled_at: l.labelled_at,
  };
}

export function resolve(labelsIn: Label[], adj?: Adjudication | null): Resolved {
  const labels = [...labelsIn].sort((a, b) => a.labeller.localeCompare(b.labeller));
  if (adj && adj.basis === basisOf(labels)) {
    return {
      state: "resolved",
      resolution: "adjudicated",
      gold: {
        item_id: adj.item_id,
        status: adj.status,
        ...(adj.skip_reason ? { skip_reason: adj.skip_reason } : {}),
        findings: adj.status === "skip" ? [] : adj.findings,
        labeller: `gold:adjudicated:${adj.adjudicator}`,
        labelled_at: adj.adjudicated_at,
        note: adj.reason,
      },
    };
  }
  if (labels.length === 0) return { state: "unlabelled" };
  if (labels.length === 1) return { state: "resolved", resolution: "single", gold: goldFrom(labels[0], "single") };

  const groups = new Map<string, Label[]>();
  for (const l of labels) groups.set(answerKey(l), [...(groups.get(answerKey(l)) ?? []), l]);
  if (groups.size === 1) return { state: "resolved", resolution: "agreed", gold: goldFrom(labels[0], "agreed") };

  const top = [...groups.values()].sort((a, b) => b.length - a.length)[0];
  const strict = top.length * 2 > labels.length;
  if (labels.length >= 3 && strict) {
    const d = dangerKey(top[0]);
    if (labels.every((l) => dangerKey(l) === d)) {
      return { state: "resolved", resolution: "majority", gold: goldFrom(top[0], "majority") };
    }
    return { state: "pending", why: adj ? "labels changed since the decision" : "danger signs differ" };
  }
  const why = adj
    ? "labels changed since the decision"
    : new Set(labels.map(dangerKey)).size > 1
      ? "danger signs differ"
      : labels.some((l) => l.status === "skip") && labels.some((l) => l.status !== "skip")
        ? "skip vs label"
        : "findings differ";
  return { state: "pending", why };
}

/** Why labellers disagree, by kind, so unclear rules show up without reading every item. */
export type Cause = "skip vs label" | "nothing vs finding" | "same finding, different assertion" | "different findings" | "danger signs differ";

export function causesOf(labels: Label[]): Cause[] {
  const out = new Set<Cause>();
  for (let x = 0; x < labels.length; x++) {
    for (let y = x + 1; y < labels.length; y++) {
      const A = labels[x], B = labels[y];
      if (answerKey(A) === answerKey(B)) continue;
      if (dangerKey(A) !== dangerKey(B)) out.add("danger signs differ");
      if ((A.status === "skip") !== (B.status === "skip")) { out.add("skip vs label"); continue; }
      if (A.status === "skip") continue;
      if (!A.findings.length || !B.findings.length) { out.add("nothing vs finding"); continue; }
      const ca = new Map(A.findings.map((f) => [f.concept, f.assertion]));
      const shared = B.findings.filter((f) => ca.has(f.concept));
      if (shared.some((f) => ca.get(f.concept) !== f.assertion)) out.add("same finding, different assertion");
      if (shared.length !== A.findings.length || shared.length !== B.findings.length) out.add("different findings");
    }
  }
  return [...out];
}

/** Plain-language pointer to the guideline rule behind each cause (shown to the admin). */
export const CAUSE_HINT: Record<Cause, string> = {
  "skip vs label": "Guidelines §10.6: skip only garbled, cut-off or other-language clips.",
  "nothing vs finding": "Guidelines §10.1–10.2: is the speaker talking about their own health, or giving general advice?",
  "same finding, different assertion": "Guidelines §2: present / absent / possible / past, and the cue words.",
  "different findings": "Guidelines §2: severity pairs and swelling site; §10.4 vocabulary only.",
  "danger signs differ": "Goes to the clinician every time. Check §1.3 (cautious reading) if it is frequent.",
};
