import { z } from "zod";

// Reviewers live in the REVIEWERS environment variable (set in Vercel, never in git):
//   [{"id":"malik","name":"Malik","role":"admin","code":"…"}, …]
// Generate it with `npm run make-codes`. Codes are compared by SHA-256 digest in
// constant time, so timing does not reveal how much of a guess was right.

export const Role = z.enum(["admin", "clinician", "annotator"]);
export type Role = z.infer<typeof Role>;

const ReviewerSchema = z.object({
  id: z.string().regex(/^[a-z0-9-]{2,32}$/),
  name: z.string().min(1).max(60),
  role: Role,
  code: z.string().min(12),
});
export type Reviewer = z.infer<typeof ReviewerSchema>;
export type PublicReviewer = Omit<Reviewer, "code">;

const DEV_REVIEWERS: Reviewer[] = [
  { id: "admin", name: "Malik", role: "admin", code: "dev-admin-code" },
  { id: "nurse", name: "Nurse", role: "clinician", code: "dev-nurse-code" },
  { id: "student", name: "Student", role: "annotator", code: "dev-student-code" },
];

let cache: { raw: string | undefined; list: Reviewer[] } | null = null;

export function reviewers(): Reviewer[] {
  const raw = process.env.REVIEWERS;
  if (cache && cache.raw === raw) return cache.list;
  let list: Reviewer[];
  if (!raw) {
    if (process.env.NODE_ENV === "production") throw new Error("REVIEWERS must be set in production");
    list = DEV_REVIEWERS;
  } else {
    list = z.array(ReviewerSchema).min(1).parse(JSON.parse(raw));
    const ids = new Set(list.map((r) => r.id));
    if (ids.size !== list.length) throw new Error("REVIEWERS has duplicate ids");
  }
  cache = { raw, list };
  return list;
}

export function publicReviewer(r: Reviewer): PublicReviewer {
  return { id: r.id, name: r.name, role: r.role };
}

export function findReviewer(id: string): Reviewer | undefined {
  return reviewers().find((r) => r.id === id);
}

async function digest(s: string): Promise<Uint8Array> {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
}

function equalBytes(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

export async function reviewerForCode(code: string): Promise<Reviewer | undefined> {
  const probe = await digest(code.trim());
  let match: Reviewer | undefined;
  for (const r of reviewers()) {
    // check every reviewer (no early exit) to keep timing independent of position
    if (equalBytes(probe, await digest(r.code))) match = r;
  }
  return match;
}
