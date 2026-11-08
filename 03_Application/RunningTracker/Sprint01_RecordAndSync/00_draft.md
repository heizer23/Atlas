# RunningTracker Sprint 01 (02a) – Record, Sync and History

Scope: Phases A+B of the "RunningTracker & Native Ghost Runner" plan. Routes/intervals (02b), Ghost (02c) and WorkoutTracker link (02d) are later sprints, but 02a must not block them (see §9).

**Principle: Atlas prepares and stores the run. AtlasPhone executes it.**

## 1. Cross-layer note (R-OPS-BP-01)

This sprint spans two layers:
- `03_Application/RunningTracker` – backend, DB schema, web UI (this folder holds the sprint docs).
- `01_System/AtlasPhone` – native pairing, sync client, Running Screen. Native API docs go to `01_System/AtlasPhone/Sprint02_RunningScreen/RunningScreen_API.md`.

Numbering: RunningTracker Sprint01 = AtlasPhone Sprint02. No domain logic enters `02_Platform`.

## 2. Goal

Prepare a run in Atlas, record it natively (GPS + optional Polar H10) with AtlasPhone, sync it to Atlas over Tailscale, and inspect it in RunningTracker history with charts.

Milestone: record an ordinary run outdoors, see it in Atlas.

## 3. Preconditions (gate)

Sprint 01 hardware tests still open: ≥20 min outdoor capture, screen locked, Bluetooth drop/reconnect, kill/resume. One real 20-min locked-screen capture is done and recorded in `MobilePlatform_API.md` **before** the Running Screen is declared done. It also provides the first real data.

Verify Sprint 01 samples carry `elapsedRealtimeNanos` (location) and a monotonic stamp (HR). If not, add them additively (new nullable fields; existing captures stay valid).

## 4. Out of scope

Maps and tiles (route stored later as geometry only), routes, interval plans, ghost, WorkoutTracker link, Polar Flow, any web↔app bridge (postMessage/loopback stay removed), push of live data.

## 5. Native access: pairing and auth

Tailscale gives private connectivity; it is not authentication.

**Pairing flow**
1. Atlas web (behind existing Google/Cloudflare auth): "Pair phone" → server creates a one-time code (8 chars, unambiguous alphabet, TTL 5 min, single use). Stored hashed. Shown as text and QR.
2. AtlasPhone pairing screen: type or scan the code, enter device name → `POST /api/runningtracker/device/pair {code, device_name}` over Tailscale.
3. Server returns a random 256-bit device token (stored hashed, with device name, created, last_used, revoked_at).
4. Phone stores the token encrypted with an Android Keystore key (AES-GCM). Never in logs, URLs, deep links or files.
5. All native calls use `Authorization: Bearer <token>`.

**Rules**
- The token authorizes the RunningTracker native endpoints only (§7), scoped to the owning user.
- Pair endpoint is the only unauthenticated one: rate-limited, locks the code after 5 wrong attempts, generic error text.
- Atlas lists paired devices (name, last used) with a Revoke button. Revoked token → 401 → phone shows "re-pair".
- Native endpoints are reachable only via the Tailscale interface, not the public Cloudflare route. Concrete mechanism (nginx listener bound to the tailnet address vs. separate server block) decided in design; the public proxy must not forward `/api/runningtracker/native/*`.
- HTTPS to the tailnet name (MagicDNS + Tailscale cert, or pinned internal CA – decide in design). No cleartext.
- Tailscale must be running on the phone for sync; the Running Screen shows connection state but a run never depends on it.

## 6. Launch: pull model, with push as optional

Primary (required): Atlas creates a *prepared run* (server-side, short id, TTL). The native Running Screen (opened from the launcher shortcut or an in-app button) lists prepared runs and downloads one → stored locally → can be started offline. Free Run needs no preparation.

Optional spike (≤1 h, hardware): "Start Run" in the web page via `intent://` link from inside the TWA. Document the result in the API doc. If it fails, nothing else changes. Carries only the short id, never credentials.

## 7. Backend (FastAPI, PostgreSQL schema `runningtracker`)

Follow StorageTracker/TaskTracker patterns (pool, platform_contracts, platform_errorhandling, shell registration, schema.sql idempotent + migrations).

Tables (final names at design):
- `runs` – id (client-generated UUID, stable), run_type (`continuous` only in 02a, column allows `interval`), planned/started/finished UTC, elapsed_s, moving_s, distance_m, status (`prepared|uploading|complete`), comment, device_id, created_at.
- `run_samples` – run_id, stream (`location|heart_rate`), seq, payload (raw as recorded, nullable fields stay null), UNIQUE(run_id, stream, seq). Raw only; never overwritten.
- `run_pauses` – run_id, started/ended (UTC + elapsed offsets) – needed for moving time now and the ghost pause rule later.
- `run_metrics` – derived (splits, pace series, avg HR, algo_version), recomputable from samples.
- `devices`, `pairing_codes` (hashed).
- Extension points for later sprints are not created yet, but `runs.route_id` (nullable, no FK until 02b) is reserved.

Endpoints
- Web (existing user auth): list/detail runs, charts data, edit comment, delete run, create prepared run, pair-code create, device list/revoke.
- Native (device token):
  - `GET /native/prepared-runs`, `GET /native/prepared-runs/{id}`
  - `POST /native/runs/{id}/begin` – create/confirm run row (idempotent)
  - `PUT /native/runs/{id}/samples` – bounded batch (≤2000 samples), idempotent on (run, stream, seq); response `{stored, high_seq per stream}`
  - `POST /native/runs/{id}/finish {metadata, expected_counts per stream, last_seq}` – server verifies counts/contiguity, computes metrics, sets `complete`; returns verified counts. Missing → `incomplete` with the gaps listed; phone re-sends.
- Ownership checked on every call; run id from another device/user → 404.

## 8. Native (AtlasPhone)

New: pairing screen, `AtlasClient` (HTTPS, Bearer, timeouts, no logging of secrets), Running Screen, upload worker.

**Running Screen** (native Compose, high contrast, keep-screen-on, uses existing `MobilePlatform` — no new GPS/BLE code)
- Before start: GPS status, H10 status (optional, GPS-only run allowed), prepared-run info, "Free Run".
- While recording: elapsed, distance, current pace (smoothed), average pace, heart rate, GPS quality, HR connection state. Pause / Resume / Finish (confirm).
- Pause is manual and distinct from poor GPS or missing HR.
- Foreground service from Sprint 01 stays the recording owner; screen recreation reattaches to the active capture.

**Metrics** (pure Kotlin, unit-tested; raw samples untouched)
- Distance: filter fixes by accuracy (drop > ~30 m), drop implausible speed jumps, ignore while paused; no naive sum of every delta.
- Current pace: smoothing window (~10 s); average pace on moving time.
- Splits per km. Elevation only if altitude accuracy is available; otherwise absent.
- Monotonic time for session durations; UTC only for persisted stamps.

**Lifecycle**: `prepared → recording ⇄ paused → completed_local → pending_upload → synced`. Stored in the capture metadata (extend the existing CaptureStore, don't replace it). Upload worker: retry with backoff, resumes from server `high_seq`, acks local samples only after the server's finish verification. Failed upload stays `pending_upload` and visible. Incomplete (killed) captures are offered "Recover / Discard" – never auto-finalized.

**Finish**: stop, drain buffer, store metadata, compute initial stats, attempt sync, short summary (shows "synced" vs "pending sync" clearly), link back to RunningTracker.

## 9. Forward compatibility (no work now)

- Samples keep raw values + seq so ghost profiles (progress→time/HR and time→progress/HR) can later be derived server-side from `run_samples`.
- Pause intervals stored so the ghost rule "moving time, pauses removed from both clocks" is computable later.
- Ghost display (02c) will show: time gap at same position, lead in metres at same time, ghost HR at same position, ghost HR at same time. Missing HR stays "–".

## 10. Web UI

Registered in the Atlas shell; existing design system and chart conventions; no new design system.
- **Run**: Free Run / prepare, pair phone, devices.
- **History**: date, distance, duration, avg pace, avg HR, sync state.
- **Run detail**: distance/duration, pace over time, HR over time, km splits, comment. **No map.**

## 11. Acceptance

Automated
- [ ] Backend: pairing (expiry, single use, lockout, revoke), auth scoping, idempotent sample upload (duplicate batch → no dupes), finish verification (gap detection), metrics, ownership.
- [ ] Native JVM: metrics filter/pace/splits, lifecycle transitions, upload resume logic, token storage wrapper.
- [ ] Sprint 01 tests still pass, lint clean.

Physical device (reported separately from automated)
- [ ] Pair the phone; revoke and re-pair.
- [ ] Prepared run downloads; Free Run works with Atlas unreachable.
- [ ] 20-min outdoor run with H10, screen locked part of the time.
- [ ] Temporary Bluetooth loss; run keeps recording, HR gap stays a gap.
- [ ] Finish offline → pending; reconnect Tailscale → synced; counts match.
- [ ] Re-sending an upload creates no duplicates.
- [ ] Run visible in History with charts.
- [ ] TWA launcher, Google login, notifications unchanged.

Do not mark a device test passed unless performed.

## 12. Security notes

- No new public ports/routes; native API tailnet-only; pairing endpoint rate-limited.
- Device token hashed server-side, Keystore-encrypted on phone, revocable, scoped.
- Location/HR data is personal: delete-run available; no samples in logs.

## 13. Open decisions for design

1. Tailnet exposure mechanism and TLS certificate source.
2. Sample storage: row per sample vs. batched JSONB (volume ≈ 2 rows/s; row-per-sample acceptable).
3. Where the Pair/Run pages live in shell navigation.

## Definition of Done

A run prepared or started on the phone is recorded with GPS (+H10 if present), survives screen lock and Bluetooth drops, syncs verified and idempotently to Atlas over Tailscale with device-token auth, and appears in RunningTracker history with pace/HR charts. Atlas owns the history; AtlasPhone owns the live run.
