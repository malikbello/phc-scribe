import { publicReviewer, reviewers } from "@/lib/reviewers";
import { allReviews, itemsById, queueStats } from "@/lib/repo";
import { REVIEW_TOTAL } from "@/lib/content";
import { handle, json, requireReviewer } from "@/lib/server";
import { store } from "@/lib/store";

export async function GET() {
  return handle(async () => {
    await requireReviewer(["admin"]);
    const team = reviewers().map(publicReviewer);
    const ids = team.map((t) => t.id);
    const queues = [];
    for (const qid of await store().smembers("queues")) {
      const st = await queueStats(qid, ids);
      const items = await itemsById(qid, st.agreement.disagreements.slice(0, 50).map((d) => d.itemId));
      queues.push({
        ...st,
        agreement: {
          ...st.agreement,
          disagreements: st.agreement.disagreements.slice(0, 50).map((d) => ({ ...d, transcript: items[d.itemId]?.transcript })),
        },
      });
    }
    const reviews = await allReviews(ids);
    const reviewDone = Object.fromEntries(ids.map((id) => [id, Object.keys(reviews[id]).length]));
    return json({ team, queues, reviewDone, reviewTotal: REVIEW_TOTAL });
  });
}
