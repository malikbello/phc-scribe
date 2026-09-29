import { myHistory } from "@/lib/repo";
import { handle, json, requireReviewer } from "@/lib/server";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  return handle(async () => {
    const r = await requireReviewer();
    const { id } = await ctx.params;
    return json({ itemIds: await myHistory(id, r.id) });
  });
}
