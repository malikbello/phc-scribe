import { beforeEach, describe, expect, it } from "vitest";
import { agreement, cohensKappa } from "@/lib/agreement";
import { candidates, pickDouble } from "@/lib/assign";
import { reviewerForCode } from "@/lib/reviewers";
import type { Label } from "@/lib/schema";
import { LabelInput, evidenceInTranscript } from "@/lib/schema";
import { displayName } from "@/lib/names";
import { signSession, verifySession } from "@/lib/session";
import { evidenceFor, tap, tokenize } from "@/lib/spans";

describe("session", () => {
  const secret = "x".repeat(40);
  it("round-trips and rejects tampering and expiry", async () => {
    const tok = await signSession({ rid: "nurse", exp: Math.floor(Date.now() / 1000) + 60 }, secret);
    expect((await verifySession(tok, secret))?.rid).toBe("nurse");
    expect(await verifySession(tok, "y".repeat(40))).toBeNull();
    const [body, sig] = tok.split(".");
    const forged = btoa(JSON.stringify({ rid: "admin", exp: 9e9 })).replace(/=+$/, "");
    expect(await verifySession(`${forged}.${sig}`, secret)).toBeNull();
    expect(await verifySession(`${body}.`, secret)).toBeNull();
    const old = await signSession({ rid: "nurse", exp: 1 }, secret);
    expect(await verifySession(old, secret)).toBeNull();
  });
});

describe("reviewer codes", () => {
  it("matches the dev codes and rejects others", async () => {
    expect((await reviewerForCode("dev-nurse-code"))?.id).toBe("nurse");
    expect((await reviewerForCode(" dev-admin-code "))?.role).toBe("admin");
    expect(await reviewerForCode("dev-nurse-cod")).toBeUndefined();
  });
});

describe("tap selection", () => {
  const text = "Mo ní ẹ̀jẹ̀ ń jáde, (no headache).";
  const toks = tokenize(text);
  it("selects single words and ranges, trimming punctuation", () => {
    let r = tap(null, 2);
    expect(evidenceFor(text, toks, r)).toBe("ẹ̀jẹ̀");
    r = tap(r, 4);
    expect(evidenceFor(text, toks, r)).toBe("ẹ̀jẹ̀ ń jáde");
    expect(tap(r, 4)).toEqual({ from: 4, to: 4 });
    expect(evidenceFor(text, toks, { from: 5, to: 6 })).toBe("no headache");
    expect(tap({ from: 1, to: 1 }, 1)).toBeNull();
  });
  it("evidence is always a substring of the transcript", () => {
    for (let a = 0; a < toks.length; a++)
      for (let b = a; b < toks.length; b++) expect(evidenceInTranscript(text, evidenceFor(text, toks, { from: a, to: b }))).toBe(true);
  });
});

describe("assignment", () => {
  it("serves double items first and respects required counts", () => {
    const order = ["a", "b", "c", "d"];
    const dbl = new Set(["c"]);
    expect(candidates(order, dbl, {}, new Set())).toEqual(["c", "a", "b", "d"]);
    expect(candidates(order, dbl, { c: 1, a: 1 }, new Set())).toEqual(["c", "b", "d"]);
    expect(candidates(order, dbl, { c: 1 }, new Set(["c"]))).toEqual(["a", "b", "d"]);
    expect(candidates(order, dbl, { c: 2 }, new Set())).toEqual(["a", "b", "d"]);
  });
  it("picks a stable double subset of the right size", () => {
    const ids = Array.from({ length: 100 }, (_, i) => `id-${i}`);
    const a = pickDouble(ids, 0.2);
    expect(a).toHaveLength(20);
    expect(pickDouble([...ids].reverse(), 0.2)).toEqual(a);
  });
});

const L = (who: string, findings: Label["findings"], status: Label["status"] = "labelled"): Label => ({
  item_id: "x", status, findings, labeller: who, labelled_at: "2026-10-01T00:00:00Z",
});
const f = (concept: string, assertion: "present" | "absent" | "possible" | "historical", text = "t") => ({ concept, assertion, evidence: { text } });

describe("agreement", () => {
  it("kappa basics", () => {
    expect(cohensKappa([true, false], [true, false])).toBe(1);
    expect(cohensKappa([], [])).toBeNull();
  });
  it("computes exact agreement, kappa and lists disagreements", () => {
    const res = agreement({
      i1: { a: L("a", [f("vaginal_bleeding", "present")]), b: L("b", [f("vaginal_bleeding", "present", "other words")]) },
      i2: { a: L("a", [f("fever", "present")]), b: L("b", [f("fever", "absent")]) },
      i3: { a: L("a", []), b: L("b", []) },
      i4: { a: L("a", [f("headache", "present")]) },
    });
    expect(res.items).toBe(3);
    expect(res.exact).toBeCloseTo(2 / 3);
    expect(res.disagreements.map((d) => d.itemId)).toEqual(["i2"]);
    expect(res.dangerKappa).not.toBeNull();
  });
});

describe("label validation", () => {
  it("rejects duplicate findings and skip without reason", () => {
    expect(() => LabelInput.parse({ itemId: "x", status: "skip" })).toThrow();
    expect(() => LabelInput.parse({ itemId: "x", status: "labelled", findings: [f("fever", "present"), f("fever", "present")] })).toThrow();
    expect(() => LabelInput.parse({ itemId: "x", status: "labelled", findings: [f("not_a_concept", "present")] })).toThrow();
    expect(LabelInput.parse({ itemId: "x", status: "labelled" }).findings).toEqual([]);
  });
});

describe("display names", () => {
  it("keeps honorifics with the first name", () => {
    expect(displayName("Dr Adé Okafor")).toBe("Dr Adé");
    expect(displayName("Nurse Bisi")).toBe("Nurse Bisi");
    expect(displayName("Tunde Bakare")).toBe("Tunde");
    expect(displayName("Malik")).toBe("Malik");
  });
});
