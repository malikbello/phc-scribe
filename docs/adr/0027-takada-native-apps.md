# ADR-0027: Takada on Android and iPhone as native apps (Capacitor), alongside the web app

- **Status:** Proposed (Malik, 2 Oct: "We still need the Android and the iOS stuff while still keeping the web app"). Built and checked; store accounts await Malik's decision.
- **Date:** 2026-10-05
- **Amends:** ADR-0023 (the phone app ships as a web app and as Android and iPhone apps from one codebase); takada-app `docs/operations.md`.

## Context
- **Today's Takada is a PWA.** It installs from the browser and works offline. Four gaps matter for clinics:
  - **Trust:** a web app needs the hub on HTTPS, so each phone has to trust the hub's certificate once (`docs/operations.md`). That is a fiddly step for a nurse.
  - **Offline from first launch:** a PWA must be loaded once over the network before it works offline. A native app carries its files.
  - **Storage:** a PWA's IndexedDB lives at the browser's discretion. In a native app it belongs to the app.
  - **Familiarity:** health workers and facility managers expect an app they install like any other.
- **Competitor visibility (Malik, 2 Oct):** the public web URL and its source maps expose the app. A native build hides nothing from a determined reverse-engineer, but nothing needs to be public before submission.
- **Constraints:** $0 unless Malik approves; 7 days to submission; one codebase.

## Decision
1. **Capacitor 8.5.2 wraps the same web build** (`apps/mobile/android`, `apps/mobile/ios`, `capacitor.config.ts`).
   - The web app stays as it is, deployed to Vercel and served by every hub.
   - **No second UI codebase.** React Native or Flutter would mean rewriting the app a week before submission.
2. **Native differences live in one module,** `src/lib/platform.ts`:
   - no service worker in the native apps;
   - the Android back button steps back through screens;
   - status bar and splash screen handled natively.
3. **Clinical-safety settings in the native projects:**
   - **Android:**
     - `allowBackup=false`, plus data-extraction rules that exclude everything: patient records never go to Google backups or device transfer;
     - HTTPS only (`usesCleartextTraffic=false`);
     - the only sensitive permission is the microphone.
   - **iPhone:** a microphone purpose string is set, and export compliance is declared as standard HTTPS only.
4. **Hub trust:**
   - **Phase 1 (now):** Android trusts user-installed CAs, so the existing one-time enrolment works in the app too.
   - **Phase 2 (after submission):** pairing pins the hub's CA, carried in the pairing QR code. No manual certificate step remains.
5. **CI** (`.github/workflows/native.yml`, only when the app changes):
   - **Android:** builds a debug APK, checks it (permissions, no backup, no cleartext, no source maps) and uploads it as an artifact.
   - **iOS:** builds for the simulator on `macos-26` (Xcode 26, as Capacitor 8 requires), without signing.
6. **No source maps in shipped builds.** They published the readable source on Vercel and in the APK. `robots.txt`, `noindex` meta and an `X-Robots-Tag` header keep the web app out of search engines.

## Distribution (Malik decides; costs money)
| Route | Cost | What it takes | Time |
|---|---|---|---|
| **Android APK, sideloaded** (pilot, demo) | $0 | Download the CI artifact; on the phone, allow "Install unknown apps" for the browser. A release key (kept as a GitHub secret) is needed before real use. | Today |
| **Google Play** | $25 once | New *personal* accounts need a closed test with **12 testers opted in for 14 days in a row** before production; organisation accounts (D-U-N-S number) are exempt. | ≥ 2 weeks: after submission |
| **iPhone, TestFlight / App Store** | $99/year (Apple Developer Program) | Signing and review. Without the programme, iPhones can only run a build from a Mac via Xcode (expires after 7 days). | Days (review) |
| **iPhone, web app** | $0 | Safari → Share → Add to Home Screen. | Today |

Recommendation for submission: **Android APK + web app on iPhone**. The paid store routes start after 12 Oct, once Malik approves them.

## Consequences
- One codebase serves three targets. Each web change needs `npx cap sync` before a native build; CI does this.
- The native apps are not run on a real device or emulator here (no KVM in the dev container). The pilot phones on 9 Oct are the first real-device check.
- `appId` is `dev.malikbello.takada`. It is permanent once published to a store, so it should be changed (if wanted) before the first store release.
- **Known limits:**
  - iOS stops a web-view recording when the screen locks. Nurses must keep Takada in the foreground while recording, so the app should say so. A native recorder plugin is the later fix.
  - `FLAG_SECURE`, which hides patient screens from screenshots and the app switcher, is not set yet, so screenshots for the demo still work. Turn it on before real use.
