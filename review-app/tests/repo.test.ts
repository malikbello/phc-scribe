import { beforeEach, describe, expect, it } from "vitest";
import { createQueue, itemForReviewer, listQueues, nextItem, queueStats, saveLabel, saveReview, myReview } from "@/lib/repo";
import { MemoryStore } from "@/lib/store";

const g = globalThis as unknown as { __phcStore?: unknown };

const items = Array.from({ length: 10 }, (_, i) => ({
  item_id: `it-${i}`,
  group_id: `g-${i}`,
  language: "pcm",
  source: "test",
  source_id: `${i}`,
  transcript: `Blood dey comot ${i}, no headache.`,
  hints: [],
}));

describe("repo flow", () => {
  beforeEach(() => { g.__phcStore = new MemoryStore(); });

  it("assigns, locks, saves, counts and computes agreement", async () => {
    const meta = await createQueue({ title: "Test set", items, doubleShare: 0.2, showHints: false }, "admin");
    expect(meta.double).toHaveLength(2);

    // double items come first, and both reviewers get them
    const a1 = await nextItem(meta.id, "a");
    const b1 = await nextItem(meta.id, "b");
    expect(meta.double).toContain(a1!.itemId);
    expect(b1!.itemId).toBe(a1!.itemId);

    await saveLabel(meta.id, "a", { itemId: a1!.itemId, status: "labelled", findings: [{ concept: "vaginal_bleeding", assertion: "present", evidence: { text: "Blood dey comot" } }] });
    await saveLabel(meta.id, "b", { itemId: a1!.itemId, status: "labelled", findings: [{ concept: "vaginal_bleeding", assertion: "present", evidence: { text: "Blood dey comot" } }] });

    // evidence must be long enough for grounding (same minimum as the Python pipeline)
    await expect(saveLabel(meta.id, "a", { itemId: "it-5", status: "labelled", findings: [{ concept: "fever", assertion: "present", evidence: { text: "B" } }] })).rejects.toThrow(/too short/);

    // evidence must be exact text
    await expect(saveLabel(meta.id, "a", { itemId: "it-5", status: "labelled", findings: [{ concept: "fever", assertion: "present", evidence: { text: "hot body" } }] })).rejects.toThrow(/exact text/);

    // single items are locked to one reviewer
    const seen = new Set<string>();
    for (let i = 0; i < 3; i++) {
      const a = await nextItem(meta.id, "a");
      const b = await nextItem(meta.id, "b");
      if (a && b && !meta.double.includes(a.itemId) && !meta.double.includes(b.itemId)) expect(a.itemId).not.toBe(b.itemId);
      if (a) { await saveLabel(meta.id, "a", { itemId: a.itemId, status: "labelled", findings: [] }); seen.add(a.itemId); }
    }

    // editing does not double count
    await saveLabel(meta.id, "a", { itemId: a1!.itemId, status: "labelled", findings: [] });
    const again = await itemForReviewer(meta.id, a1!.itemId, "a");
    expect(again.mine?.findings).toEqual([]);

    const stats = await queueStats(meta.id, ["a", "b"]);
    expect(stats.perReviewer.a).toBe(1 + seen.size);
    expect(stats.agreement.items).toBe(1);
    expect(stats.agreement.exact).toBe(0); // a edited to empty, b kept bleeding

    const progress = await listQueues("a");
    expect(progress[0].mineDone).toBe(1 + seen.size);
  });

  it("stores review answers per reviewer", async () => {
    await saveReview("nurse", { key: "rule:DS-001", verdict: "ok" });
    await saveReview("nurse", { key: "question:1", verdict: "answer", note: " Yes, add pallor " });
    const r = await myReview("nurse");
    expect(Object.keys(r).sort()).toEqual(["question:1", "rule:DS-001"]);
    expect(r["question:1"].note).toBe("Yes, add pallor");
    expect(await myReview("doctor")).toEqual({});
  });
});
