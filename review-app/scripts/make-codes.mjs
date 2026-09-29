#!/usr/bin/env node
// Generate SESSION_SECRET and REVIEWERS for Vercel. Run on your own machine:
//   npm run make-codes -- "Malik Bello:admin" "Nurse Adeola:clinician" "Dr Okafor:clinician" "Tunde:annotator"
// Paste the two values into Vercel > Project > Settings > Environment Variables.
// Send each person their own code privately (not in a group chat). Nothing is written to disk.
import { randomBytes } from "node:crypto";

const args = process.argv.slice(2);
if (!args.length) {
  console.error('Usage: npm run make-codes -- "Name:role" ...   (role = admin | clinician | annotator)');
  process.exit(1);
}
const words = ["ewe", "odo", "oko", "ile", "oju", "ina", "omi", "igi", "ayo", "ire", "oba", "ona"];
const code = () => {
  const b = randomBytes(10);
  const w = words[b[0] % words.length];
  return `${w}-${b.subarray(1).toString("base64url").slice(0, 12)}`;
};
const seen = new Set();
const reviewers = args.map((a) => {
  const [name, role = "annotator"] = a.split(":");
  if (!["admin", "clinician", "annotator"].includes(role)) throw new Error(`bad role: ${role}`);
  let id = name.toLowerCase().normalize("NFD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 24) || "reviewer";
  while (seen.has(id)) id += "-2";
  seen.add(id);
  return { id, name: name.trim(), role, code: code() };
});
console.log("SESSION_SECRET=" + randomBytes(32).toString("base64url"));
console.log("REVIEWERS=" + JSON.stringify(reviewers));
console.log("\nCodes to send (privately):");
for (const r of reviewers) console.log(`  ${r.name.padEnd(24)} ${r.code}`);
