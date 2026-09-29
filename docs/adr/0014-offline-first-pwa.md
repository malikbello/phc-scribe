# ADR-0014: Offline-first PWA frontend with enforced performance budgets

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Users have low-end Android phones, intermittent connectivity and mixed literacy. The design bar is premium.

## Decision
TypeScript + Preact + Vite; Workbox service worker; Dexie (IndexedDB); FormatJS (ICU). Budgets: ≤200 KB JS+CSS gzipped, interactive in ≤3 s on low-end Android over 3G. WCAG 2.2 AA enforced with axe-core in CI. Play Store packaging via a Trusted Web Activity later.

## Consequences
No native app for NAIC. Background audio and sync limits of browsers must be tested on real devices.
