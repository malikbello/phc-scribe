import { InviteInput, inviteReviewer, listReviewers } from "@/lib/reviewers";
import { assertSameOrigin, handle, json, readJson, requireReviewer } from "@/lib/server";

export async function GET() {
  return handle(async () => {
    await requireReviewer(["admin"]);
    return json({ reviewers: await listReviewers() });
  });
}

// Invite: returns the new reviewer's code ONCE. Only a keyed hash is stored.
export async function POST(req: Request) {
  return handle(async () => {
    assertSameOrigin(req);
    const admin = await requireReviewer(["admin"]);
    const input = InviteInput.parse(await readJson(req, 5_000));
    const { reviewer, code } = await inviteReviewer(input, admin.id);
    return json({ reviewer, code });
  });
}
