import { beforeEach, describe, expect, it } from "vitest";
import { CODE_ALPHABET, findReviewer, inviteReviewer, listReviewers, normaliseCode, reviewerForCode, revokeReviewer } from "@/lib/reviewers";
import { MemoryStore } from "@/lib/store";

const g = globalThis as unknown as { __phcStore?: unknown };

describe("invited reviewers", () => {
  beforeEach(() => { g.__phcStore = new MemoryStore(); });

  it("invites, signs in by code, lists and revokes", async () => {
    const { reviewer, code } = await inviteReviewer({ name: "Dr Adé Okafor", role: "clinician" }, "admin");
    expect(reviewer.id).toMatch(/^dr-ade-okafor-[a-z0-9]{4}$/);
    expect(code.length).toBeGreaterThanOrEqual(12);
    expect((await reviewerForCode(code))?.id).toBe(reviewer.id);
    expect((await reviewerForCode(` ${code} `))?.id).toBe(reviewer.id);
    expect(await reviewerForCode(code.slice(0, -1))).toBeUndefined();
    expect((await listReviewers()).map((r) => r.id)).toContain(reviewer.id);

    // the stored record never contains the code
    expect(JSON.stringify(await findReviewer(reviewer.id))).not.toContain(code);

    expect(await revokeReviewer(reviewer.id)).toBe(true);
    expect(await reviewerForCode(code)).toBeUndefined();
    expect(await findReviewer(reviewer.id)).toBeUndefined();
  });

  it("accepts a code pasted with punctuation or invisible characters around it", async () => {
    const { reviewer, code } = await inviteReviewer({ name: "Abdullah", role: "annotator" }, "admin");
    for (const pasted of [`${code},`, `${code}.`, `"${code}"`, `​${code}​`, `${code}
`, `(${code})`]) {
      expect((await reviewerForCode(pasted))?.id).toBe(reviewer.id);
    }
    expect(await reviewerForCode(`${code}x`)).toBeUndefined();
    expect(await reviewerForCode(",")).toBeUndefined();
  });

  it("issues codes without look-alike characters", async () => {
    expect(CODE_ALPHABET).not.toMatch(/[01oOlIi]/);
    for (let k = 0; k < 20; k++) {
      const { code } = await inviteReviewer({ name: `R${k}`, role: "annotator" }, "admin");
      expect(code).toMatch(/^[a-z]{3}-[23456789a-hjkmnp-zA-HJ-NP-Z]{14}$/);
      expect(normaliseCode(code)).toBe(code);
    }
  });

  it("refuses to revoke bootstrap (environment) reviewers", async () => {
    expect(await revokeReviewer("admin")).toBe(false);
    expect((await findReviewer("admin"))?.role).toBe("admin");
  });

  it("gives distinct codes and ids to people with the same name", async () => {
    const a = await inviteReviewer({ name: "Student", role: "annotator" }, "admin");
    const b = await inviteReviewer({ name: "Student", role: "annotator" }, "admin");
    expect(a.code).not.toBe(b.code);
    expect(a.reviewer.id).not.toBe(b.reviewer.id);
  });
});
