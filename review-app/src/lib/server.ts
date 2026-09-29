import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { ZodError } from "zod";
import { findReviewer, type Reviewer } from "./reviewers";
import { SESSION_COOKIE, verifySession } from "./session";

// Route-handler helpers: every response is no-store; every data route checks the
// session again (middleware is the first gate, not the only one).

export function json(data: unknown, status = 200): NextResponse {
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

export class HttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function currentReviewer(): Promise<Reviewer | null> {
  const jar = await cookies();
  const s = await verifySession(jar.get(SESSION_COOKIE)?.value);
  return s ? ((await findReviewer(s.rid)) ?? null) : null;
}

export async function requireReviewer(roles?: Reviewer["role"][]): Promise<Reviewer> {
  const r = await currentReviewer();
  if (!r) throw new HttpError(401, "Please sign in");
  if (roles && !roles.includes(r.role)) throw new HttpError(403, "Not allowed");
  return r;
}

export function handle(fn: () => Promise<NextResponse>): Promise<NextResponse> {
  return fn().catch((e: unknown) => {
    if (e instanceof HttpError) return json({ error: e.message }, e.status);
    if (e instanceof ZodError) return json({ error: e.issues.map((i) => i.message).join("; ") }, 400);
    if (e instanceof SyntaxError) return json({ error: "Invalid JSON" }, 400);
    console.error(e);
    return json({ error: "Something went wrong" }, 500);
  });
}

export async function readJson(req: Request, maxBytes = 4_000_000): Promise<unknown> {
  const len = Number(req.headers.get("content-length") ?? 0);
  if (len > maxBytes) throw new HttpError(413, "Upload too large");
  const text = await req.text();
  if (text.length > maxBytes) throw new HttpError(413, "Upload too large");
  return JSON.parse(text);
}

/** Same-origin check for state-changing requests (defence in depth on top of SameSite). */
export function assertSameOrigin(req: Request): void {
  const origin = req.headers.get("origin");
  if (!origin) return; // non-browser clients (tests, curl) send no Origin
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  if (!host || new URL(origin).host !== host) throw new HttpError(403, "Cross-site request blocked");
}
