import { saveLabel } from "@/lib/repo";
import { LabelInput } from "@/lib/schema";
import { assertSameOrigin, handle, json, readJson, requireReviewer } from "@/lib/server";

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  return handle(async () => {
    assertSameOrigin(req);
    const r = await requireReviewer();
    const { id } = await ctx.params;
    const input = LabelInput.parse(await readJson(req, 100_000));
    return json({ saved: await saveLabel(id, r.id, input) });
  });
}
