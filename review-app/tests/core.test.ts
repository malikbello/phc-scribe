import { beforeEach, describe, expect, it } from "vitest";
import { agreement, cohensKappa } from "@/lib/agreement";
import { candidates, pickDouble, teamComplete } from "@/lib/assign";
import { levelFor, levelUp } from "@/lib/game";
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

describe("calibration (everyone) mode", () => {
  it("keeps every item open to each reviewer who has not labelled it", () => {
    const order = ["a", "b", "c"];
    const counts = { a: 3, b: 1 };
    expect(candidates(order, new Set(), counts, new Set(["b"]), true)).toEqual(["a", "c"]);
    expect(candidates(order, new Set(), counts, new Set(["a", "b", "c"]), true)).toEqual([]);
    // complete for the team once two people have labelled it
    expect(teamComplete(order, new Set(), counts, true)).toBe(1);
  });
});

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

describe("agreement over several labellers", () => {
  const lab = (labeller: string, concept: string): Label => ({
    item_id: "i1", status: "labelled", labeller, labelled_at: "", findings: [{ concept, assertion: "present", evidence: { text: "x" } }],
  });
  it("compares every pair", () => {
    const res = agreement({ i1: { a: lab("a", "vaginal_bleeding"), b: lab("b", "vaginal_bleeding"), c: lab("c", "fever") } });
    expect(res.items).toBe(1);
    expect(res.pairs).toBe(3);
    expect(res.exact).toBeCloseTo(1 / 3);
    expect(res.disagreements.map((d) => d.labels.length)).toEqual([3]);
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

describe("review content", () => {
  it("frames every open question and orders the tabs rules-first", async () => {
    const { QUESTIONS, QUESTION_CONTEXT, REVIEW_SECTIONS } = await import("@/lib/content");
    expect(QUESTIONS.length).toBe(Object.keys(QUESTION_CONTEXT).length);
    QUESTIONS.forEach((_, i) => expect(QUESTION_CONTEXT[i + 1]?.ask).toBeTruthy());
    expect(REVIEW_SECTIONS.map((s) => s.id)).toEqual(["rule", "concept", "question", "phrase", "medicine", "freeze"]);
  });

  it("gives each role its own sign-off steps", async () => {
    const { MEDICATIONS, REVIEW_KEYS, reviewKeysFor, sectionsFor } = await import("@/lib/content");
    expect(MEDICATIONS.map((m) => m.id)).toEqual(["iron_folic_acid", "ipt_sp", "tetanus_diphtheria", "deworming", "calcium"]);
    expect(sectionsFor("annotator")).toEqual([]);
    expect(sectionsFor("pharmacist").map((s) => s.id)).toEqual(["medicine"]);
    const pharm = reviewKeysFor("pharmacist");
    expect(pharm.size).toBe(MEDICATIONS.length + 2);
    expect([...pharm].every((k) => k.startsWith("medicine"))).toBe(true);
    expect(reviewKeysFor("clinician")).toEqual(REVIEW_KEYS);
    expect(reviewKeysFor("admin")).toEqual(REVIEW_KEYS);
  });
});


describe("game levels", () => {
  it("counts levels of 25 and names ranks", () => {
    expect(levelFor(0)).toEqual({ level: 1, rank: "Listener", intoLevel: 0, toNext: 25 });
    expect(levelFor(26)).toMatchObject({ level: 2, rank: "Note-taker", intoLevel: 1, toNext: 24 });
    expect(levelFor(1000).rank).toBe("Master scribe");
  });
  it("detects a level-up only when crossing a boundary", () => {
    expect(levelUp(24, 25)?.level).toBe(2);
    expect(levelUp(25, 26)).toBeNull();
  });
});
