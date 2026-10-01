import { reviewKeysFor } from "@/lib/content";
import { myReview, saveReview } from "@/lib/repo";
import { ReviewAnswer } from "@/lib/schema";
import { assertSameOrigin, handle, HttpError, json, readJson, requireReviewer } from "@/lib/server";

export async function GET() {
  return handle(async () => {
    const r = await requireReviewer();
    return json({ role: r.role, answers: await myReview(r.id) });
  });
}

export async function POST(req: Request) {
  return handle(async () => {
    assertSameOrigin(req);
    const r = await requireReviewer();
    const answer = ReviewAnswer.parse(await readJson(req, 20_000));
    if (!reviewKeysFor(r.role).has(answer.key)) throw new HttpError(403, "This sign-off step isn't part of your role");
    return json({ saved: await saveReview(r.id, answer) });
  });
}
