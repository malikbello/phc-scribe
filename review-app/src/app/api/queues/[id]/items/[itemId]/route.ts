import { itemForReviewer } from "@/lib/repo";
import { handle, json, requireReviewer } from "@/lib/server";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string; itemId: string }> }) {
  return handle(async () => {
    const r = await requireReviewer();
    const { id, itemId } = await ctx.params;
    return json({ item: await itemForReviewer(id, decodeURIComponent(itemId), r.id) });
  });
}
