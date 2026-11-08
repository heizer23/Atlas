# Sprint 01 (revised) — AtlasPhone Native Mobile Platform

Status: DRAFT for approval — revision of the original "Native Mobile Platform & Sensor Bridge" sprint.
Revised 2026-11-08 after on-device findings (below). Nothing in this document is implemented yet.

## Why the sprint changed

The original sprint exposed GPS and Polar H10 data to the React app in Chrome through a native<->web bridge.
On the real phone (Chrome 156, TWA, 2026-11-08):

| Attempt | Result |
|---|---|
| TWA postMessage (`requestPostMessageChannel`) | Chrome returns `false` for every variant tried (before launch, after navigation, with/without target origin, after `warmup()`, `PostMessageService` declared). Origin validation itself succeeded. No reason is logged by Chrome. |
| Authenticated loopback WebSocket (127.0.0.1) | Server works (15 JVM tests). The page's connection stays pending forever — Chrome holds requests to the phone's own loopback (Local Network Access), a TWA cannot show the permission prompt, disabling the flag did not help, and an `atlas://` link from the TWA does not launch the app. |

Conclusion: a page-to-app link inside Chrome is the wrong dependency for this feature. A native app can read the
sensors, buffer, and later upload without involving the browser at all, and it can keep recording with the screen off.

Decision (user, 2026-11-08): **hybrid** — the running experience (ghost run) is a native Android screen inside
AtlasPhone; everything else (planning, statistics, history) stays in the normal Atlas web app. Smooth switching between
the two is explicitly NOT a requirement; a ghost run is started deliberately and the web app is used afterwards.

## Objective

Provide a reusable native Mobile Platform in AtlasPhone (Kotlin) that acquires GPS and Polar H10 heart-rate data,
manages the Android permissions, and keeps the samples in a durable local capture buffer, plus a native diagnostic
screen that exercises all of it on the physical phone.

The later RunningTracker sprint consumes this platform (native ghost-run screen, route download, run upload) and owns
all domain logic and server persistence. Run statistics live in the Atlas web app.

## Scope

In scope
1. Native modules, each independent: `location`, `heartrate` (BLE), `permissions`, `capture` (durable buffer).
2. Data contracts as in the original sprint (units SI, ISO-8601 UTC timestamps with ms, per-capture `sequence`, unavailable values `null`).
3. Native diagnostic screen (Compose Activity in AtlasPhone): bridge-free, shows permissions, GPS start/stop with
   lat/lon/accuracy/speed/count, HR scan/connect/BPM/status/timestamp, capture start/stop with ID and counts,
   buffered-sample retrieval check, errors and reconnection events.
4. Entry to the diagnostic screen without the web app: launcher app shortcut ("Mobile Platform test").
5. Foreground-service-ready design (acquisition not tied to the Activity lifecycle); documentation of how to run it in a
   Foreground Service. A minimal foreground service MAY be included if time permits (see decision 2).
6. Documentation of the public Kotlin API, payloads, units, states, lifecycle, behaviour when closed/minimised/locked.
7. Automated tests (JVM) for protocol-independent logic: buffer ordering/idempotency/ack/bounds, heart-rate payload
   parsing, reconnection policy, permission state mapping. Physical-device tests reported separately.

Out of scope
- RunningTracker app, routes, run storage, training types, ghost logic, statistics, maps.
- Uploading to or downloading from the Atlas server (next sprint, see "Server access" below).
- Any web-side sensor bridge: the loopback server, TypeScript `MobileBridge`, the web `/mobile-test` screen and the
  Chrome permission helper are removed from the sprint (code stays in git history, commits 6f21de3..c066936).
- Polar SDK, ECG, Polar Flow, generalised notification/haptics/audio framework.
- Guaranteed screen-off recording (unless decision 2 includes the service AND it passes the outdoor test).

## Architecture

```
AtlasPhone (Android, Kotlin)
├── TWA launcher (unchanged: Atlas web app, Google auth, notifications)
└── mobile/                      Mobile Platform (no domain logic)
    ├── permissions/             central request + status, no repeated prompts after denial
    ├── location/                FusedLocationProvider, ~1 Hz, explicit start/stop
    ├── heartrate/               BLE scan/connect 0x180D/0x2A37, bounded reconnect, remembered device
    ├── capture/                 durable ordered buffer (SQLite), ack/cleanup, bounded size
    └── diagnostics/             Compose test Activity (technical tool, not the RunningTracker UI)
```

Each module exposes a small Kotlin interface plus a `Flow` of samples/state; the capture buffer subscribes to
sample flows and persists them independently of any UI. Layer note (R-OPS-BP-01): the Android project lives in
`01_System/AtlasPhone`; the Mobile Platform is a package inside it, not a separate component. If a separate Platform
module is wanted later it can be extracted as a Gradle module without API changes.

## Server access (decision for the next sprint, documented now, NOT built here)

The phone must reach the Atlas server from outside the house to upload runs and fetch ghost routes. `workout.linspad.net`
is behind Cloudflare Access; the existing token-registration call (`/api/devices/token`) is already unverified from outside.
Options, least exposure first (R-OPS-BP-02):
1. Tailscale on host and phone; ingest/route endpoints reachable only on the private network, per-device token. No public
   exposure, no Cloudflare change. (Previously preferred for notifications as well.)
2. Cloudflare Access service token for one narrow path; secret lives in the APK (extractable from the app).
3. One public bypass path with its own per-device secret and strict validation; widest exposure.
Recommendation: option 1. To be decided with the RunningTracker sprint; this sprint stays server-independent.

## Acceptance criteria (physical phone unless stated)

- [ ] AtlasPhone still launches as a TWA; Atlas navigation and Google login unchanged.
- [ ] Diagnostic screen opens from the launcher shortcut and works without the Atlas web app.
- [ ] Permissions requested only when a capability is first used; denial shown clearly, no repeated prompts; revocation handled.
- [ ] GPS start/stop; real coordinates, accuracy, speed, timestamps; updates ~1/s while active; none after stop (resources released).
- [ ] Polar H10 discovered, connected, live BPM updating continuously with timestamps; scan stops when not needed.
- [ ] Temporary Bluetooth loss: bounded reconnect, manual reconnect, no crash; Bluetooth-off handled.
- [ ] Capture buffer: samples ordered with unique sequence; survive Activity restart and process death; retrieval without
      duplicates; explicit ack and cleanup; unacknowledged data never auto-deleted; bounded size with defined overflow behaviour.
- [ ] 20-minute outdoor test of stable foreground recording (screen on) or gaps documented explicitly.
- [ ] No new exposed ports or listeners; no new web-origin access to native code; existing deployment/install workflow unchanged.
- [ ] Automated tests pass; hardware features are reported as verified ONLY if tested on the phone.

## Delivery

Summary of modules; public API documentation; payloads/units/timestamps/errors/lifecycle; how RunningTracker subscribes;
behaviour when closed/minimised/screen-locked; automated vs physical test results separately; limitations.

## Decisions needed from the user

1. Approve this scope (hybrid, no web bridge, no server upload in this sprint).
2. Include a minimal Foreground Service now (screen-off recording, adds a persistent notification and Android 14+
   foreground-service-type permissions), or keep it as documentation only for now? Recommendation: include it — for a
   native recorder it is small and is what makes a real run reliable.
3. Server access option for the next sprint (recommended: Tailscale).
