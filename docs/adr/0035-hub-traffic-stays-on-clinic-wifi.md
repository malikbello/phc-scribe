# ADR-0035: Keep hub traffic on the clinic Wi-Fi on Android

- **Status:** Proposed (11 Oct 2026), for after v1.
- **Date:** 2026-10-11
- **Changes:** takada-app's Android app (a small native plugin) and its error messages. The web app and the hub are unchanged.

## Context
The clinic hub's Wi-Fi has **no internet**. That is the point: the laptop hotspot works offline.

Android treats a Wi-Fi network without internet as second best. In the 10 Oct pilot on a Galaxy S22, Samsung's "Switch to mobile data" setting sent requests for `https://192.168.137.1` over **mobile data**, where the hub does not exist. The app could not reach the hub until mobile data was turned off.

The v1 workaround is a phone setting, done once at enrolment ([takada-app `docs/operations.md`](https://github.com/malikbello/takada-app/blob/main/docs/operations.md)): keep the Wi-Fi connection, with "Switch to mobile data" off. A clinic should not depend on every nurse's phone settings.

## Decision (after v1)
1. **Native Android app: bind hub requests to the Wi-Fi network.**
   - A Capacitor plugin finds the connected Wi-Fi network (`NetworkCapabilities.TRANSPORT_WIFI`), whether or not Android has validated its internet.
   - It sends requests for the paired hub through that network (`Network.openConnection`, or a socket factory bound to it).
   - Only hub traffic is bound. Anything else on the phone keeps Android's normal routing.
2. **If no Wi-Fi network carries the hub's address,** the app says so plainly: "Not connected to the clinic Wi-Fi (`<hub name>`)." It does not report "Can't reach the hub".
3. **Web app (PWA):** a browser cannot choose the network. The app keeps the enrolment step and adds a diagnostic: when the hub fails while the phone reports mobile data, it suggests "Turn off mobile data, or keep the clinic Wi-Fi in Settings".
4. **Test before it ships:** the S22 (Samsung's "Switch to mobile data" on), one low-cost Android phone, and the hotspot without internet. Recordings, drafts and sync must all work with mobile data on.

## Consequences
- **Less setup:** nurses no longer need a phone setting, which removes the most likely first-day failure in a clinic.
- **Cost:**
  - native code in one more place, so the plugin needs its own tests;
  - Apple's iOS has the same issue in a milder form (its "Wi-Fi Assist"); it gets the same treatment when the iPhone app is used.
- **Still needed:** the hub laptop's hotspot must not switch itself off (Windows "Power saving" off, [takada-app `docs/operations.md`](https://github.com/malikbello/takada-app/blob/main/docs/operations.md)).
