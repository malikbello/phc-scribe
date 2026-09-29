import { NextResponse } from "next/server";
import { listReviewers, publicReviewer } from "@/lib/reviewers";
import { allLabels, allReviews, getMeta } from "@/lib/repo";
import { handle, HttpError, requireReviewer } from "@/lib/server";

// ?kind=labels&queue=<id>  -> JSONL, one Label per line (feeds scripts/build_s4_items.py)
// ?kind=review             -> JSON of every reviewer's clinical-review answers

export async function GET(req: Request) {
  return handle(async () => {
    await requireReviewer(["admin"]);
    const url = new URL(req.url);
    const kind = url.searchParams.get("kind");
    const stamp = new Date().toISOString().slice(0, 10);
    if (kind === "labels") {
      const qid = url.searchParams.get("queue") ?? "";
      const meta = await getMeta(qid);
      const labels = await allLabels(qid);
      const lines = Object.values(labels).flatMap((byReviewer) => Object.values(byReviewer)).map((l) => JSON.stringify(l));
      return new NextResponse(lines.join("\n") + (lines.length ? "\n" : ""), {
        headers: {
          "Content-Type": "application/jsonl; charset=utf-8",
          "Content-Disposition": `attachment; filename="labels.${meta.id}.${stamp}.jsonl"`,
          "Cache-Control": "no-store",
        },
      });
    }
    if (kind === "review") {
      const team = (await listReviewers()).map(publicReviewer);
      const body = { exported_at: new Date().toISOString(), team, answers: await allReviews(team.map((t) => t.id)) };
      return new NextResponse(JSON.stringify(body, null, 2), {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Content-Disposition": `attachment; filename="clinical-review.${stamp}.json"`,
          "Cache-Control": "no-store",
        },
      });
    }
    throw new HttpError(400, "kind must be labels or review");
  });
}
