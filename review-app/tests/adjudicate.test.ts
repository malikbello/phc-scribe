import { beforeEach, describe, expect, it } from "vitest";
import { basisOf, causesOf, resolve, type Adjudication } from "@/lib/adjudicate";
import { adjudicationState, createQueue, nextPending, saveAdjudication, saveLabel } from "@/lib/repo";
import type { Finding, Label } from "@/lib/schema";
import { MemoryStore } from "@/lib/store";

const f = (concept: string, assertion: Finding["assertion"], text = "Blood dey comot"): Finding => ({ concept, assertion, evidence: { text } });
const lab = (labeller: string, findings: Finding[], status: Label["status"] = "labelled"): Label => ({
  item_id: "x", status, findings, labeller, labelled_at: "2026-10-01T00:00:00Z", ...(status === "skip" ? { skip_reason: "unintelligible" as const } : {}),
});

describe("resolve", () => {
  it("settles single, agreed and safe majorities by rule", () => {
    expect(resolve([])).toEqual({ state: "unlabelled" });
    expect(resolve([lab("a", [])])).toMatchObject({ state: "resolved", resolution: "single" });
    expect(resolve([lab("a", [f("fever", "present")]), lab("b", [f("fever", "present", "hot")])])).toMatchObject({ resolution: "agreed", gold: { labeller: "gold:agreed" } });
    expect(resolve([lab("a", [], "skip"), lab("b", [], "skip")])).toMatchObject({ resolution: "agreed" });
    // 3 of 4 say nothing; the odd one has a non-danger finding: majority
    const r = resolve([lab("a", []), lab("b", []), lab("c", []), lab("d", [f("cough", "present")])]);
    expect(r).toMatchObject({ resolution: "majority", gold: { findings: [] } });
  });

  it("sends every danger-sign split and every two-way split to the clinician", () => {
    expect(resolve([lab("a", []), lab("b", []), lab("c", []), lab("d", [f("vaginal_bleeding", "present")])])).toEqual({ state: "pending", why: "danger signs differ" });
    expect(resolve([lab("a", []), lab("b", [f("cough", "present")])])).toEqual({ state: "pending", why: "findings differ" });
    expect(resolve([lab("a", [], "skip"), lab("b", [])])).toEqual({ state: "pending", why: "skip vs label" });
    // no strict majority among 4
    expect(resolve([lab("a", []), lab("b", []), lab("c", [f("cough", "present")]), lab("d", [f("cough", "present")])]).state).toBe("pending");
  });

  it("uses the clinician's decision until the labels change", () => {
    const labels = [lab("a", []), lab("b", [f("vaginal_bleeding", "present")])];
    const adj: Adjudication = { item_id: "x", status: "labelled", findings: [], reason: "general talk", adjudicator: "nurse", adjudicated_at: "t", basis: basisOf(labels) };
    expect(resolve(labels, adj)).toMatchObject({ resolution: "adjudicated", gold: { labeller: "gold:adjudicated:nurse", findings: [] } });
    const changed = [labels[0], lab("b", [f("vaginal_bleeding", "possible")])];
    expect(resolve(changed, adj)).toEqual({ state: "pending", why: "labels changed since the decision" });
  });

  it("names the causes of disagreement", () => {
    expect(causesOf([lab("a", []), lab("b", [f("cough", "present")])])).toEqual(["nothing vs finding"]);
    expect(causesOf([lab("a", [f("cough", "present")]), lab("b", [f("cough", "possible")])])).toEqual(["same finding, different assertion"]);
    expect(causesOf([lab("a", [], "skip"), lab("b", [f("vaginal_bleeding", "present")])]).sort()).toEqual(["danger signs differ", "skip vs label"]);
  });
});

const g = globalThis as unknown as { __phcStore?: unknown };
const items = Array.from({ length: 3 }, (_, i) => ({ item_id: `it-${i}`, group_id: `g-${i}`, language: "pcm", source: "wazobia", source_id: `${i}`, transcript: `Blood dey comot ${i}, I no get fever.`, hints: [] }));

describe("adjudication flow", () => {
  beforeEach(() => { g.__phcStore = new MemoryStore(); });

  it("queues only real disagreements, records the decision and exports gold", async () => {
    const meta = await createQueue({ title: "Practice", items, doubleShare: 0, showHints: false, everyone: true }, "admin");
    const bleed = [{ concept: "vaginal_bleeding", assertion: "present" as const, evidence: { text: "Blood dey comot" } }];
    for (const rid of ["a", "b", "c"]) await saveLabel(meta.id, rid, { itemId: "it-0", status: "labelled", findings: [] });
    for (const rid of ["a", "b"]) await saveLabel(meta.id, rid, { itemId: "it-1", status: "labelled", findings: [] });
    await saveLabel(meta.id, "c", { itemId: "it-1", status: "labelled", findings: bleed });

    let st = await adjudicationState(meta.id);
    expect(st.counts).toMatchObject({ agreed: 1, pending: 1, unlabelled: 1 });
    const p = await nextPending(meta.id);
    expect(p).toMatchObject({ itemId: "it-1", why: "danger signs differ" });
    expect(p!.answers.map((a) => a.count).sort()).toEqual([1, 2]);
    expect(JSON.stringify(p)).not.toMatch(/"labeller"/); // anonymised

    await expect(saveAdjudication(meta.id, "nurse", { itemId: "it-1", status: "labelled", findings: [{ ...bleed[0], evidence: { text: "not in text" } }], reason: "bleeding" })).rejects.toThrow(/exact text/);
    await saveAdjudication(meta.id, "nurse", { itemId: "it-1", status: "labelled", findings: bleed, reason: "A danger sign was missed" });
    st = await adjudicationState(meta.id);
    expect(st.counts).toMatchObject({ agreed: 1, adjudicated: 1, pending: 0 });
    expect(st.gold.find((l) => l.item_id === "it-1")).toMatchObject({ labeller: "gold:adjudicated:nurse", findings: bleed, note: "A danger sign was missed" });
    expect(await nextPending(meta.id)).toBeNull();
  });
});
