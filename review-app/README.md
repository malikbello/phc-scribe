# PHC Scribe Review

A private, tap-first web app where the team (clinical adviser, doctor, students, Malik) signs off the clinical rules and labels benchmark items. Built with Next.js on Vercel, with data in Upstash Redis.

- **Clinical sign-off:** every danger-sign rule, finding, note phrasing and open question as a card. Tap *Looks right* or *Needs change*; answers save on each tap.
- **Labelling:** tap the words, tap the finding, tap *Present / Absent / Possible / Past pregnancy*, then *Save & next*. The quoted evidence is always exact text from the item. 20% of items (configurable) go to two people so we can report agreement (Cohen's kappa).
- **Admin:** invite and revoke reviewers (no redeploy), upload a queue file, watch progress and agreement, read disagreements, export labels (JSONL for `scripts/build_s4_items.py`) and sign-off answers (JSON).

## Security
- Each person signs in with their own access code. Bootstrap admins live in the `REVIEWERS` environment variable in Vercel; everyone else is invited from *Admin → Team*. An invite code is shown once, and only an HMAC-SHA256 hash of it (keyed with `SESSION_SECRET`) is stored. Nothing is ever in git.
- Revoking someone (Admin → Team → Revoke) ends their access at their next request.
- Sessions are HMAC-signed, HttpOnly, Secure and SameSite=Lax cookies (14 days). Every API route re-checks the session and the role; admin routes are admin-only.
- Benchmark items are **never** in the code or the page bundle. The admin uploads them into Redis, and they are served only to signed-in reviewers. Reviewers see their own labels, not each other's.
- Cross-site writes are refused (Origin check). Failed sign-ins are rate-limited per IP (10 per 15 minutes).
- Strict security headers: CSP with no third-party origins, frame-ancestors none, noindex, no-referrer, HSTS. Responses are `no-store`.
- No analytics, no external fonts, no third-party scripts.

## Deploy (one time, about 10 minutes)
1. **Import:** in Vercel, go to *Add New… → Project*, import `malikbello/phc-scribe` and set **Root Directory** to `review-app`. Framework: Next.js (auto-detected).
2. **Storage:** in the project, open *Storage → Create/Connect → Upstash for Redis* (free plan) and connect it to all environments. This adds `KV_REST_API_URL` and `KV_REST_API_TOKEN` automatically.
3. **Codes:** on your own computer, run:
   ```bash
   cd review-app && npm install
   npm run make-codes -- "Malik Bello:admin" "Nurse Name:clinician" "Dr Name:clinician" "Student Name:annotator"
   ```
   In *Settings → Environment Variables*, add `SESSION_SECRET` and `REVIEWERS` exactly as printed, for the Production environment. Send each person **their own** code privately.
4. **Production branch:** in *Settings → Git*, set the production branch to the branch you deploy from (`main` once `day1-2-gate1` is merged).
5. **Deploy:** redeploy once so the new variables apply. Open the production URL and sign in with your admin code.

Roles: `admin` sees everything, uploads and exports; `clinician` does sign-off and labelling; `annotator` does labelling only.

## CI/CD
- **CD:** Vercel's GitHub integration deploys every push to the production branch automatically; other branches get preview URLs (which Vercel protects by default). `vercel.json` skips builds when nothing in `review-app/` changed.
- **CI:** `.github/workflows/ci.yml` (job `review-app`) runs type checks, unit tests, a production build and `npm audit` on every push. To stop broken code going live, protect the production branch in GitHub and require the `review-app` check.

## Scaling
- **Reviewers:** no limit in practice; invite from the admin screen. Work is handed out one item at a time, with 15-minute locks so two people never get the same single-label item. Double-labelled items go to exactly two different people.
- **Items:** tested for sets of hundreds; the design holds to about 5,000 items per set (the item order and double-label subset are stored in the set's metadata). Admin statistics read all labels in pipelined batches (one round trip per 200 items).
- **Upstash free plan:** 500k commands a month. A label costs about 8 commands, so the free plan covers tens of thousands of labels.
- **Monitoring:** `GET /api/health` returns `{"ok":true}` when Redis is reachable (for an uptime monitor). It reveals nothing else.

## Day-to-day
- **Add a set:** *Admin → Add a labelling set*, then upload a queue file (`data/private/label_queue.*.jsonl`).
- **Fix a set before anyone starts:** *Delete set* appears on a set until its first label; re-upload with new settings (use a 100% double-labelled share for a calibration round).
- **Export labels:** *Admin → Labels (JSONL)*, then `python scripts/build_s4_items.py <file>` builds gold items (use `--labeller` for each annotator's set).
- **Review content:** after changing the vocabulary, rules or phrase bank, run `python scripts/export_review_data.py` (CI fails if you forget).
- **Add someone:** *Admin → Team → Invite*, then send them the code privately.
- **Revoke someone:** *Admin → Team → Revoke* (invited people), or remove them from `REVIEWERS` and redeploy (bootstrap people).

## Local development
```bash
cd review-app && npm install && npm run dev   # http://localhost:3000
```
Without Redis or `REVIEWERS` it uses an in-memory store and dev codes (`dev-admin-code`, `dev-nurse-code`, `dev-student-code`). Production refuses to start without real configuration.
