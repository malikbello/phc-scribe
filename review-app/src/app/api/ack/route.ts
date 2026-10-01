import { z } from "zod";
import { saveAck } from "@/lib/repo";
import { AckStep } from "@/lib/schema";
import { assertSameOrigin, handle, json, readJson, requireReviewer } from "@/lib/server";

export async function POST(req: Request) {
  return handle(async () => {
    assertSameOrigin(req);
    const r = await requireReviewer();
    const { step } = z.object({ step: AckStep }).parse(await readJson(req, 1_000));
    await saveAck(r.id, step);
    return json({ ok: true });
  });
}
