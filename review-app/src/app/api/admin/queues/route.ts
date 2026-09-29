import { createQueue } from "@/lib/repo";
import { QueueUpload } from "@/lib/schema";
import { assertSameOrigin, handle, json, readJson, requireReviewer } from "@/lib/server";

export async function POST(req: Request) {
  return handle(async () => {
    assertSameOrigin(req);
    const r = await requireReviewer(["admin"]);
    const up = QueueUpload.parse(await readJson(req));
    const meta = await createQueue(up, r.id);
    return json({ queue: { id: meta.id, title: meta.title, items: meta.order.length, double: meta.double.length } });
  });
}
