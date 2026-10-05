import { z } from "zod";
import { sessionSecret } from "./session";
import { store } from "./store";

// Two sources of reviewers:
// - Bootstrap: the REVIEWERS environment variable (set in Vercel, never in git). Use it
//   for the admin(s); changing it needs a redeploy.
// - Invited: created from the admin screen and stored in Redis, so the team can grow
//   without a redeploy. Only a keyed hash of each code is stored (HMAC-SHA256 with
//   SESSION_SECRET); the code itself is shown once, at invite time.
// Sign-in looks the code up by its hash, so it is O(1) and does not leak timing about
// how close a guess was.

export const Role = z.enum(["admin", "clinician", "pharmacist", "annotator"]);
export type Role = z.infer<typeof Role>;

const EnvReviewer = z.object({
  id: z.string().regex(/^[a-z0-9-]{2,40}$/),
  name: z.string().min(1).max(60),
  role: Role,
  code: z.string().min(12),
});

export type Reviewer = {
  id: string;
  name: string;
  role: Role;
  source: "env" | "invite";
  createdAt?: string;
  createdBy?: string;
};
export type PublicReviewer = Pick<Reviewer, "id" | "name" | "role">;

const DEV_REVIEWERS = [
  { id: "admin", name: "Malik", role: "admin" as const, code: "dev-admin-code" },
  { id: "nurse", name: "Nurse", role: "clinician" as const, code: "dev-nurse-code" },
  { id: "pharmacist", name: "Pharmacist", role: "pharmacist" as const, code: "dev-pharmacist-code" },
  { id: "student", name: "Student", role: "annotator" as const, code: "dev-student-code" },
];

const K = {
  all: "reviewers", // hash id -> Reviewer (invited only)
  code: (hash: string) => `codeidx:${hash}`, // -> reviewer id
  codeOf: (id: string) => `codeof:${id}`, // -> code hash (for revocation)
};

let envCache: { raw: string | undefined; list: z.infer<typeof EnvReviewer>[] } | null = null;

function envReviewers(): z.infer<typeof EnvReviewer>[] {
  const raw = process.env.REVIEWERS;
  if (envCache && envCache.raw === raw) return envCache.list;
  let list: z.infer<typeof EnvReviewer>[];
  if (!raw) {
    if (process.env.NODE_ENV === "production") throw new Error("REVIEWERS must be set in production");
    list = DEV_REVIEWERS;
  } else {
    list = z.array(EnvReviewer).min(1).parse(JSON.parse(raw));
    if (new Set(list.map((r) => r.id)).size !== list.length) throw new Error("REVIEWERS has duplicate ids");
  }
  envCache = { raw, list };
  return list;
}

function fromEnv(r: z.infer<typeof EnvReviewer>): Reviewer {
  return { id: r.id, name: r.name, role: r.role, source: "env" };
}

export function publicReviewer(r: Reviewer): PublicReviewer {
  return { id: r.id, name: r.name, role: r.role };
}

/**
 * Codes reach reviewers through chat apps, which can add punctuation or invisible characters
 * around them when copied ("omi-…," or a trailing full stop). A code is only letters, digits and
 * one inner hyphen, so anything else at either end is dropped. Codes issued before this change
 * normalise to themselves, so their stored hashes still match.
 */
export function normaliseCode(code: string): string {
  return code.normalize("NFKC").replace(/^[^A-Za-z0-9]+|[^A-Za-z0-9]+$/g, "");
}

async function codeHash(code: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(sessionSecret()),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(normaliseCode(code))));
  return Array.from(sig, (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function listReviewers(): Promise<Reviewer[]> {
  const invited = Object.values(await store().hgetall<Reviewer>(K.all));
  const env = envReviewers().map(fromEnv);
  const envIds = new Set(env.map((r) => r.id));
  return [...env, ...invited.filter((r) => !envIds.has(r.id)).sort((a, b) => a.name.localeCompare(b.name))];
}

export async function findReviewer(id: string): Promise<Reviewer | undefined> {
  const env = envReviewers().find((r) => r.id === id);
  if (env) return fromEnv(env);
  return (await store().hget<Reviewer>(K.all, id)) ?? undefined;
}

export async function reviewerForCode(code: string): Promise<Reviewer | undefined> {
  const probe = normaliseCode(code);
  if (!probe) return undefined;
  const hash = await codeHash(probe);
  // Env codes are hashed the same way, so every comparison is between fixed-length digests.
  for (const r of envReviewers()) if ((await codeHash(r.code)) === hash) return fromEnv(r);
  const id = await store().get<string>(K.code(hash));
  return id ? findReviewer(id) : undefined;
}

const WORDS = ["ewe", "odo", "oko", "ile", "oju", "ina", "omi", "igi", "ayo", "ire", "oba", "ona", "ofe", "iwa"];

// No look-alikes (0/O/o, 1/l/I/i), so a code read off a phone screen can be typed correctly.
export const CODE_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ";
const CODE_LENGTH = 14; // 55 symbols ^ 14 is about 81 bits

/** Uniform random index below n (rejection sampling, so no modulo bias). */
function randomIndex(n: number): number {
  const limit = 256 - (256 % n);
  for (;;) {
    const [x] = crypto.getRandomValues(new Uint8Array(1));
    if (x < limit) return x % n;
  }
}

function newCode(): string {
  const tail = Array.from({ length: CODE_LENGTH }, () => CODE_ALPHABET[randomIndex(CODE_ALPHABET.length)]).join("");
  return `${WORDS[randomIndex(WORDS.length)]}-${tail}`;
}

function newId(name: string): string {
  const base = name.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 24) || "reviewer";
  const rnd = Array.from(crypto.getRandomValues(new Uint8Array(3)), (x) => x.toString(36).padStart(2, "0")).join("").slice(0, 4);
  return `${base}-${rnd}`;
}

export const InviteInput = z.object({ name: z.string().trim().min(1).max(60), role: Role });

/** Create a reviewer and return their one-time code. */
export async function inviteReviewer(input: z.infer<typeof InviteInput>, by: string): Promise<{ reviewer: Reviewer; code: string }> {
  const s = store();
  const reviewer: Reviewer = { id: newId(input.name), name: input.name, role: input.role, source: "invite", createdAt: new Date().toISOString(), createdBy: by };
  const code = newCode();
  const hash = await codeHash(code);
  await s.hset(K.all, { [reviewer.id]: reviewer });
  await s.set(K.code(hash), reviewer.id);
  await s.set(K.codeOf(reviewer.id), hash);
  return { reviewer, code };
}

/** Revoke an invited reviewer: their code stops working and their session ends at the next request. */
export async function revokeReviewer(id: string): Promise<boolean> {
  const s = store();
  if (envReviewers().some((r) => r.id === id)) return false; // env reviewers change via Vercel settings
  const hash = await s.get<string>(K.codeOf(id));
  if (hash) await s.del(K.code(hash));
  await s.del(K.codeOf(id));
  await s.hdel(K.all, id);
  return true;
}
