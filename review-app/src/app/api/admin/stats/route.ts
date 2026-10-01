import { listReviewers, publicReviewer } from "@/lib/reviewers";
import { adjudicationState, allReviews, itemsById, queueStats } from "@/lib/repo";
import { reviewKeysFor } from "@/lib/content";
import { handle, json, requireReviewer } from "@/lib/server";
import { store } from "@/lib/store";

export async function GET() {
  return handle(async () => {
    await requireReviewer(["admin"]);
    const team = (await listReviewers()).map(publicReviewer);
    const ids = team.map((t) => t.id);
    const queues = [];
    for (const qid of await store().smembers("queues")) {
      const st = await queueStats(qid, ids);
      const items = await itemsById(qid, st.agreement.disagreements.slice(0, 50).map((d) => d.itemId));
      const adj = await adjudicationState(qid);
      queues.push({
        ...st,
        gold: { counts: adj.counts, causes: adj.causes },
        agreement: {
          ...st.agreement,
          disagreements: st.agreement.disagreements.slice(0, 50).map((d) => ({ ...d, transcript: items[d.itemId]?.transcript })),
        },
      });
    }
    const reviews = await allReviews(ids);
    // Progress per member over the sign-off steps of their role.
    const reviewDone: Record<string, number> = {};
    const reviewTotal: Record<string, number> = {};
    for (const t of team) {
      const keys = reviewKeysFor(t.role);
      reviewDone[t.id] = Object.keys(reviews[t.id]).filter((k) => keys.has(k)).length;
      reviewTotal[t.id] = keys.size;
    }
    return json({ team, queues, reviewDone, reviewTotal });
  });
}
