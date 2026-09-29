import { z } from "zod";
import { revokeReviewer } from "@/lib/reviewers";
import { assertSameOrigin, handle, HttpError, json, readJson, requireReviewer } from "@/lib/server";

const Body = z.object({ id: z.string().min(1).max(60) });

export async function POST(req: Request) {
  return handle(async () => {
    assertSameOrigin(req);
    const admin = await requireReviewer(["admin"]);
    const { id } = Body.parse(await readJson(req, 2_000));
    if (id === admin.id) throw new HttpError(400, "You can't revoke yourself");
    if (!(await revokeReviewer(id))) throw new HttpError(400, "This person is set in Vercel (REVIEWERS); remove them there");
    return json({ ok: true });
  });
}
