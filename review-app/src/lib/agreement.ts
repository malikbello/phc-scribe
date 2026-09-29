import { DANGER_IDS } from "./content";
import type { Label } from "./schema";

// Inter-annotator agreement on double-labelled items (first two labellers per item,
// by reviewer id). Reported: exact agreement on the full finding set, Cohen's kappa on
// danger-sign positivity over (item x danger concept), and pairwise F1 on
// (concept, assertion) pairs. Items either labeller skipped count as disagreements
// unless both skipped.

const POSITIVE = new Set(["present", "possible"]);

function pairs(l: Label): Set<string> {
  return new Set(l.findings.map((f) => `${f.concept}|${f.assertion}`));
}

function dangerPositive(l: Label): Set<string> {
  return new Set(l.findings.filter((f) => DANGER_IDS.has(f.concept) && POSITIVE.has(f.assertion)).map((f) => f.concept));
}

export type Agreement = {
  items: number;
  exact: number | null;
  dangerKappa: number | null;
  pairF1: number | null;
  disagreements: { itemId: string; labels: Label[] }[];
};

export function cohensKappa(a: boolean[], b: boolean[]): number | null {
  const n = a.length;
  if (!n) return null;
  let both = 0, onlyA = 0, onlyB = 0, neither = 0;
  for (let i = 0; i < n; i++) {
    if (a[i] && b[i]) both++;
    else if (a[i]) onlyA++;
    else if (b[i]) onlyB++;
    else neither++;
  }
  const po = (both + neither) / n;
  const pa = (both + onlyA) / n, pb = (both + onlyB) / n;
  const pe = pa * pb + (1 - pa) * (1 - pb);
  if (pe === 1) return po === 1 ? 1 : null;
  return (po - pe) / (1 - pe);
}

export function agreement(byItem: Record<string, Record<string, Label>>): Agreement {
  let exact = 0, items = 0, tp = 0, fp = 0, fn = 0;
  const ka: boolean[] = [], kb: boolean[] = [];
  const disagreements: Agreement["disagreements"] = [];
  for (const [itemId, labels] of Object.entries(byItem)) {
    const ids = Object.keys(labels).sort();
    if (ids.length < 2) continue;
    const A = labels[ids[0]], B = labels[ids[1]];
    items++;
    const bothSkip = A.status === "skip" && B.status === "skip";
    const pa = pairs(A), pb = pairs(B);
    const same = bothSkip || (A.status === B.status && pa.size === pb.size && [...pa].every((p) => pb.has(p)));
    if (same) exact++;
    else disagreements.push({ itemId, labels: ids.map((i) => labels[i]) });
    if (A.status === "labelled" && B.status === "labelled") {
      for (const p of pa) (pb.has(p) ? tp++ : fp++);
      for (const p of pb) if (!pa.has(p)) fn++;
      const da = dangerPositive(A), db = dangerPositive(B);
      for (const c of DANGER_IDS) {
        ka.push(da.has(c));
        kb.push(db.has(c));
      }
    }
  }
  const f1 = tp + fp + fn === 0 ? (items ? 1 : null) : (2 * tp) / (2 * tp + fp + fn);
  return {
    items,
    exact: items ? exact / items : null,
    dangerKappa: cohensKappa(ka, kb),
    pairF1: f1,
    disagreements,
  };
}
