import { nextItem } from "@/lib/repo";
import { handle, json, requireReviewer } from "@/lib/server";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  return handle(async () => {
    const r = await requireReviewer();
    const { id } = await ctx.params;
    return json({ item: await nextItem(id, r.id) });
  });
}
