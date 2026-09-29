import { myReview, saveReview } from "@/lib/repo";
import { ReviewAnswer } from "@/lib/schema";
import { assertSameOrigin, handle, json, readJson, requireReviewer } from "@/lib/server";

export async function GET() {
  return handle(async () => {
    const r = await requireReviewer();
    return json({ answers: await myReview(r.id) });
  });
}

export async function POST(req: Request) {
  return handle(async () => {
    assertSameOrigin(req);
    const r = await requireReviewer();
    const answer = ReviewAnswer.parse(await readJson(req, 20_000));
    return json({ saved: await saveReview(r.id, answer) });
  });
}
