import { DANGER_IDS } from "./content";
import type { Label } from "./schema";

// Inter-annotator agreement over every pair of labellers on each multiply-labelled item
// (two per item for double-label subsets; everyone on calibration sets). Reported:
// exact agreement on the full finding set (share of pairs), Cohen's kappa on danger-sign
// positivity over (pair x danger concept), and pairwise F1 on (concept, assertion)
// pairs. A pair where one labeller skipped counts as a disagreement unless both skipped.

const POSITIVE = new Set(["present", "possible"]);

function pairs(l: Label): Set<string> {
  return new Set(l.findings.map((f) => `${f.concept}|${f.assertion}`));
}

function dangerPositive(l: Label): Set<string> {
  return new Set(l.findings.filter((f) => DANGER_IDS.has(f.concept) && POSITIVE.has(f.assertion)).map((f) => f.concept));
}

export type Agreement = {
  items: number;
  pairs: number;
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
  let exact = 0, items = 0, pairCount = 0, tp = 0, fp = 0, fn = 0;
  const ka: boolean[] = [], kb: boolean[] = [];
  const disagreements: Agreement["disagreements"] = [];
  for (const [itemId, labels] of Object.entries(byItem)) {
    const ids = Object.keys(labels).sort();
    if (ids.length < 2) continue;
    items++;
    let itemAgrees = true;
    for (let x = 0; x < ids.length; x++) {
      for (let y = x + 1; y < ids.length; y++) {
        const A = labels[ids[x]], B = labels[ids[y]];
        pairCount++;
        const bothSkip = A.status === "skip" && B.status === "skip";
        const pa = pairs(A), pb = pairs(B);
        const same = bothSkip || (A.status === B.status && pa.size === pb.size && [...pa].every((p) => pb.has(p)));
        if (same) exact++;
        else itemAgrees = false;
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
    }
    if (!itemAgrees) disagreements.push({ itemId, labels: ids.map((i) => labels[i]) });
  }
  const f1 = tp + fp + fn === 0 ? (pairCount ? 1 : null) : (2 * tp) / (2 * tp + fp + fn);
  return {
    items,
    pairs: pairCount,
    exact: pairCount ? exact / pairCount : null,
    dangerKappa: cohensKappa(ka, kb),
    pairF1: f1,
    disagreements,
  };
}
