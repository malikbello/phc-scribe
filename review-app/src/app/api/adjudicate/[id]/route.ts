import { nextPending, saveAdjudication } from "@/lib/repo";
import { AdjudicationInput } from "@/lib/schema";
import { assertSameOrigin, handle, json, readJson, requireReviewer } from "@/lib/server";

// GET ?after=<itemId>: the next disagreement to settle (answers anonymised).
export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  return handle(async () => {
    await requireReviewer(["clinician", "admin"]);
    const { id } = await ctx.params;
    const after = new URL(req.url).searchParams.get("after") ?? undefined;
    return json({ item: await nextPending(id, after) });
  });
}

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  return handle(async () => {
    assertSameOrigin(req);
    const r = await requireReviewer(["clinician", "admin"]);
    const { id } = await ctx.params;
    const input = AdjudicationInput.parse(await readJson(req, 100_000));
    return json({ saved: await saveAdjudication(id, r.id, input) });
  });
}
