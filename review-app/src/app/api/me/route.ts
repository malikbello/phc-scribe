import { publicReviewer } from "@/lib/reviewers";
import { listQueues, myAcks, pendingCounts, reviewProgress } from "@/lib/repo";
import { handle, json, requireReviewer } from "@/lib/server";

export async function GET() {
  return handle(async () => {
    const r = await requireReviewer();
    // Disagreements waiting for a decision: only the clinician (and admin) settle them.
    const settle = r.role === "clinician" || r.role === "admin" ? await pendingCounts() : [];
    return json({ reviewer: publicReviewer(r), queues: await listQueues(r.id), review: await reviewProgress(r.id, r.role), acks: await myAcks(r.id), settle });
  });
}
