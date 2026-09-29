import { publicReviewer } from "@/lib/reviewers";
import { listQueues, reviewProgress } from "@/lib/repo";
import { handle, json, requireReviewer } from "@/lib/server";

export async function GET() {
  return handle(async () => {
    const r = await requireReviewer();
    return json({ reviewer: publicReviewer(r), queues: await listQueues(r.id), review: await reviewProgress(r.id) });
  });
}
