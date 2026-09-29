import { NextResponse } from "next/server";
import { z } from "zod";
import { publicReviewer, reviewerForCode } from "@/lib/reviewers";
import { assertSameOrigin, handle, HttpError, readJson } from "@/lib/server";
import { SESSION_COOKIE, SESSION_TTL_SECONDS, signSession } from "@/lib/session";
import { store } from "@/lib/store";

const Body = z.object({ code: z.string().min(1).max(200) });

export async function POST(req: Request) {
  return handle(async () => {
    assertSameOrigin(req);
    const ip = (req.headers.get("x-forwarded-for") ?? "local").split(",")[0].trim();
    // Only failed attempts count, so a team sharing one clinic Wi-Fi can't lock itself out.
    const key = `rl:login:${ip}`;
    if (Number((await store().get<number>(key)) ?? 0) >= 10) {
      throw new HttpError(429, "Too many attempts. Try again in 15 minutes.");
    }
    const { code } = Body.parse(await readJson(req, 10_000));
    const reviewer = await reviewerForCode(code);
    if (!reviewer) {
      await store().incrWithTtl(key, 15 * 60);
      throw new HttpError(401, "That code didn't work. Check it and try again.");
    }
    const token = await signSession({ rid: reviewer.id, exp: Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS });
    const res = NextResponse.json({ reviewer: publicReviewer(reviewer) }, { headers: { "Cache-Control": "no-store" } });
    res.cookies.set(SESSION_COOKIE, token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: SESSION_TTL_SECONDS,
    });
    return res;
  });
}
