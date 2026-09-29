import { store } from "@/lib/store";

// Public liveness check for uptime monitoring. Reveals nothing but ok/degraded.
export async function GET() {
  let ok = false;
  try {
    ok = await store().ping();
  } catch {
    ok = false;
  }
  return Response.json({ ok }, { status: ok ? 200 : 503, headers: { "Cache-Control": "no-store" } });
}
