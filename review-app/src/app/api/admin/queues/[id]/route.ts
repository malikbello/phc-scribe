import { deleteQueue } from "@/lib/repo";
import { assertSameOrigin, handle, json, requireReviewer } from "@/lib/server";

export async function DELETE(req: Request, ctx: { params: Promise<{ id: string }> }) {
  return handle(async () => {
    assertSameOrigin(req);
    await requireReviewer(["admin"]);
    const { id } = await ctx.params;
    await deleteQueue(id);
    return json({ ok: true });
  });
}
