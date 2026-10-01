import { deleteQueue, setEveryone } from "@/lib/repo";
import { QueuePatch } from "@/lib/schema";
import { assertSameOrigin, handle, json, readJson, requireReviewer } from "@/lib/server";

export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  return handle(async () => {
    assertSameOrigin(req);
    await requireReviewer(["admin"]);
    const { id } = await ctx.params;
    const { everyone } = QueuePatch.parse(await readJson(req, 1_000));
    const meta = await setEveryone(id, everyone);
    return json({ queue: { id: meta.id, everyone: Boolean(meta.everyone) } });
  });
}

export async function DELETE(req: Request, ctx: { params: Promise<{ id: string }> }) {
  return handle(async () => {
    assertSameOrigin(req);
    await requireReviewer(["admin"]);
    const { id } = await ctx.params;
    await deleteQueue(id);
    return json({ ok: true });
  });
}
