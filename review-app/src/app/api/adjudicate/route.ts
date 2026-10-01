import { pendingCounts } from "@/lib/repo";
import { handle, json, requireReviewer } from "@/lib/server";

// Sets with disagreements waiting for the clinician's decision.
export async function GET() {
  return handle(async () => {
    await requireReviewer(["clinician", "admin"]);
    return json({ queues: await pendingCounts() });
  });
}
