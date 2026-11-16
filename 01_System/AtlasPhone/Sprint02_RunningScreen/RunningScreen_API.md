# AtlasPhone Running Screen, pairing and sync

Sprint: AtlasPhone Sprint 02 = RunningTracker Sprint01_RecordAndSync (`03_Application/RunningTracker/Sprint01_RecordAndSync/`).
Code: `app/src/main/java/net/linspad/atlasphone/running/`. Principle: *Atlas prepares and stores the run, AtlasPhone executes it.*
No web bridge (no postMessage, no loopback); the TWA launcher (`MainActivity`) and the FCM service are unchanged.

Status tags: **[tested: JVM]** automated (`./gradlew :app:testDebugUnitTest`), **[built]** compiles and lints, NOT run on hardware,
**[unverified]** needs the physical phone, Tailscale or an outdoor run. **Nothing on hardware has been verified in this sprint.**

## Entry points

- Launcher shortcut "Running Screen" (long-press the AtlasPhone icon) -> `ui/RunningActivity` (`exported=false`). **[built]**
- Pairing screen (`ui/PairingScreen`) is shown when the phone has no token; "Not now" leaves Free Run available. **[built]**
- Summary (`ui/RunningScreen.SummaryScreen`) after Finish: shows "Synced to Atlas" or "Pending sync" (refreshed every 2 s) and an
  "Open in Atlas" link `atlas://running/history/<run id>` (handled by `MainActivity`; carries only the run id). **[built]**

## Pairing and token (`auth/`)

1. Atlas web: Running > Devices > *Pair phone* shows an 8-character one-time code (TTL 5 min, single use) as text and QR.
2. Phone: type/paste the code, or scan the QR with the Google code scanner (`ui/PairingScreen`), enter the https server URL
   (prefilled from the QR) and a device name -> `POST <base>/api/runningtracker/native/pair {code, device_name}`.
3. The server returns a random 256-bit device token once. `TokenStore` stores it **only** as AES-GCM ciphertext (Android Keystore
   key `atlasphone_run_token`) in the prefs file `atlas_run_pairing`, which is excluded from backup together with `mobile_captures.db`
   (`res/xml/backup_rules.xml`, `data_extraction_rules.xml`). The token is never logged and never put into a URL, deep link or file.
4. All native calls send `Authorization: Bearer <token>` (except pair). A 401 means the token was revoked: the run is kept,
   `RunMeta.needsRepair` is set and the Running Screen offers "Re-pair this phone".

| Piece | Status |
|---|---|
| `PairingPayload.parse` (`ATLASRUN1\|<https url>\|<code>` or bare code; http refused; alphabet check) | [tested: JVM] |
| `TokenStore` with a fake cipher: round trip, no plaintext in prefs, clear, corrupt blob -> null, non-https refused | [tested: JVM] |
| `KeystoreAesGcmCipher` (real Android Keystore AES-GCM) | [built], [unverified] on a device |
| QR scan with `play-services-code-scanner` | [built], [unverified] on a device |
| Pair / revoke / re-pair against the real server over Tailscale | [unverified] |

The QR prefix literal `ATLASRUN1` exists in three places: `backend/config.py`, `src/pairingPayload.ts` and `auth/PairingPayload.kt`;
the Kotlin parser and the pytest/Playwright suites each pin it.

## AtlasClient (`net/AtlasClient.kt`)

HTTPS only: the constructor throws `IllegalArgumentException` for any other scheme (no `network_security_config`; cleartext is also
blocked by the platform default). `HttpTransport` is injected (`UrlConnectionTransport`: connect 10 s, read 30 s). No headers, bodies or
tokens are logged or put into exception messages. Calls (`<base>/api/runningtracker/native/...`):

| Method | Path | Result |
|---|---|---|
| `pair(code, deviceName)` | `POST /pair` (no auth) | `PairResult` |
| `preparedRuns()` / `preparedRun(id)` | `GET /prepared-runs[/{id}]` | `PreparedRun` |
| `begin(runId, startedAtMillis)` | `POST /runs/{id}/begin` | `BeginResult(status, contiguousSeq)` |
| `putSamples(runId, samples)` | `PUT /runs/{id}/samples` (stream `location.sample` -> `location`, `heartRate.sample` -> `heart_rate`; payload unchanged) | `SamplesResult` |
| `finish(runId, meta, counts, lastSeq, dropped)` | `POST /runs/{id}/finish` | `FinishResult(complete, missingRanges, mismatchedStreams)` |

`AtlasResult`: `Success`, `Unauthorized` (401), `NotFound` (404), `Rejected` (other 4xx, server code/message), `ServerError` (5xx or
unparsable 2xx), `NetworkError`. Status mapping, Bearer rule, stream mapping, https-only and "no token in results" **[tested: JVM]**
with a fake transport. Real TLS to the tailnet name **[unverified]**.

Server side of this contract: `03_Application/RunningTracker/Sprint01_RecordAndSync/10_architecture.json` (endpoints, V1 finish
verification, R1 resume cursors) and `backend/routers/native.py`. The native API is reachable only through the tailnet mount
(`make runningtracker-tailnet-up`, human step, see `01_System/Access/Tailscale/readme.md`); the public shell proxy answers 404.
**[unverified]** from the phone.

## Lifecycle (`RunLifecycle`, `RunModels`)

`prepared -> recording <-> paused -> [recovery ->] completed_local -> pending_upload -> synced` (`recovery` since RunningTracker Sprint02, see below). A Free Run enters at `recording`; recovery of an
interrupted capture enters at `paused`. Illegal transitions return `null`. The state lives in `RunMeta`, persisted as JSON in the new
`CaptureStore.run_meta` table (key = capture id = server run id). **[tested: JVM]** (all events x all states, JSON round trip).

`CaptureStore` is now database version 2: `onUpgrade` only adds `run_meta`; captures, samples and every Sprint 01 method are unchanged.
`deleteCapture` also removes the run's `run_meta` row. A hand-built version-1 database upgrades without losing captures or samples
**[tested: JVM]**. Sample payloads gained a nullable `elapsedRealtimeNanos` (monotonic stamp) for location and heart-rate samples;
existing captures stay valid (draft section 3 check: the stamps were missing and are now additive). Mapping **[tested: JVM]**,
`Location.elapsedRealtimeNanos` / `SystemClock.elapsedRealtimeNanos()` at notification arrival **[built]**.

## Run finish, recovery and recap (RunningTracker Sprint02)

Design: `03_Application/RunningTracker/Sprint02_RunFinishAndRecovery/` (invariants P1, L1, RS1, HR1, HR2, HRR1, ST1, C1).

- **Lifecycle.** New state `RECOVERY`, new events `FINISH_RUN` (RECORDING|PAUSED -> RECOVERY), `FINISH_TRAINING` (RECOVERY -> COMPLETED_LOCAL) and
  `RECOVER` from RECOVERY (stays RECOVERY). The one-step `FINISH` stays and is used when `RecoveryGate.offersRecovery(currentHr)` is false (no live
  heart rate at the button press): the button then reads "Finish" and no recovery phase starts. **[tested: JVM]**
- **Finish Run** (`RunController.finishRun`): GPS stops (`location.stop()` only; recorder, HR and foreground service continue), the final running
  `RunSummary`, splits and ghost standing are persisted once; `RunMeta.runFinishedAtMillis` = end of running, `finishedAtMillis` stays null until
  Finish Training. **Finish Training** (`finishTraining`): `stopAll`, HRR over all stored HR, recap rebuilt (standing carried over), upload enqueued;
  the running summary is not recomputed. Controller flows **[built]**, summary/recap assembly **[tested: JVM]** (`RecapBuilderTest`).
- **RunMeta keys** (all optional, old metas decode): `runFinishedAtMillis`, `recovery` (HRR scalars), `recap` (standing, running-phase splits and max
  HR, 1-second-bucket HR series over running + recovery). **[tested: JVM]** (`RunMetaCompatTest`)
- **HR smoothing** is display only (`hr/HrSmoothing.kt`): Raw / 5 s (default) / 10 s, setting `hr_smoothing` in SharedPreferences
  `atlas_run_settings`, never uploaded. Invalid readings (0, outside 30..230, isolated spike) are gaps, never 0. **[tested: JVM]**; the home-panel
  selector and the live screens using `LiveRunState.hrDisplay` are **[built]**.
- **HRR** (`recap/RecoveryMetrics`): HR_end, HR_60, HR_120 as medians in fixed windows around the run end, HRR = HR_end - HR_x, null when not
  computable; same values as the server through `tests/fixtures/recovery_golden.json`. **[tested: JVM]** `RecoveryTracker` (live values, 15 minute
  reminder) **[tested: JVM]**.
- **Finish body**: `run_finished_at` (ISO-8601 UTC) only when `runFinishedAtMillis` is set, omitted otherwise. **[tested: JVM]**
  **Deploy order (C1): the server must be deployed before a phone build that sends this key** (an old server answers 422 and the run stays pending).
- **Screens** (`ui/RecoveryScreen`, `ui/RecapScreen`, replaces the old summary): **[built]**, **[unverified]** on hardware.

Unverified until a real run: foreground-service behaviour with GPS stopped and the screen locked (HR must keep arriving, OQ5), H10 disconnect during
recovery, kill during recovery then Recover, no location sample after the run end on the server, recap rendering and smoothing selector on the phone.

## Metrics (`metrics/RunMetrics.kt`)

Pure Kotlin implementation of algorithm A1 (see `10_architecture.json`, invariant A1): accuracy filter (> 30 m dropped), first fix
after a pause is an anchor and adds no distance, fixes inside pauses ignored, steps < 1 m skipped, speed > 12 m/s dropped (using
`elapsedRealtimeNanos` when present), smoothed pace over 10 s, per-km splits with interpolated crossing times plus a final partial
split (>= 10 m), average heart rate outside pauses. Elevation is absent (no altitude accuracy). `RunMetricsAccumulator` feeds the live
screen; `RunMetrics.summarize/splits` rebuild from stored samples for finish and recovery. Raw samples are never modified.
Parity with the backend: both read `03_Application/RunningTracker/tests/fixtures/metrics_golden.json` (analytic expected values;
clean route, pause, GPS jump, low accuracy, stationary, GPS-only, monotonic-stamp preference). Kotlin does not compute max heart
rate or the bucketed series (the server owns those). **[tested: JVM]**. Algorithm choices where the design left room are recorded in
`00_Blueprint/Quality/agent_rule_evidence.md` (EVD-2026-11-08-001).

## Upload (`sync/`)

`UploadPlanner` (pure) decides: resume from the server's `contiguous_seq`, finish after the last batch (batches <= 1000 samples),
resend from just before the first gap for at most 3 rounds, then a visible error; 401 -> re-pair, network/5xx -> retry later,
404/4xx -> visible failure. `UploadEngine` executes the decisions against `CaptureStore` and `AtlasClient`; `UploadWorker`
(WorkManager, unique work per run, network constraint, exponential backoff 30 s) wires real objects. Local samples are acknowledged
and purged **only after** the server answered `complete` to finish. A failed upload stays `pending_upload`, visible on the Running
Screen with "Retry sync". Uploads are also re-enqueued whenever the Running Screen opens.

| Behaviour | Status |
|---|---|
| Resume from cursor, bounded batches, finish after last batch | [tested: JVM] (fake server, real SQLite) |
| No ack/purge before a verified finish; gap -> resend; 3 rounds then pending + error | [tested: JVM] |
| 401 -> needsRepair, network failure -> retry, 404 -> visible failure, local data kept | [tested: JVM] |
| WorkManager scheduling/backoff on a device | [built], [unverified] |
| Re-sending creates no duplicates (server side idempotency) | [tested: pytest] (`test_native_sync.py`); end to end [unverified] |

## Running Screen (`ui/RunningScreen.kt`, `session/RunController.kt`)

Native Compose, dark high-contrast theme, `FLAG_KEEP_SCREEN_ON`, permissions via `PermissionManager` with the same pattern as
`MobileTestActivity`. No new GPS/BLE code: `RunController` (process-wide singleton) uses `MobilePlatform` only and keeps the active
run, so recreating the screen reattaches via `live()`. The Sprint 01 `RecordingService` remains the foreground-service owner (its
notification still opens the diagnostics screen; unchanged on purpose).

- Before start: GPS and heart-rate sensor status (sensor optional, GPS-only runs are allowed), prepared runs (downloaded and stored
  locally, startable offline), **Free Run**, pending uploads with retry, Interrupted-run banner with Recover / Discard (explicit
  confirm; nothing is ever finalized automatically).
- While recording: elapsed, moving time, distance, smoothed pace, average pace, heart rate, GPS quality, HR connection state,
  Pause/Resume, Finish with confirmation. A manual pause shows a full-width yellow "PAUSED" bar and is distinct from poor GPS or a
  missing heart-rate sensor.
- Finish: drain delay (400 ms), stop recorder/GPS/HR, close open pause, summary via `RunMetrics.summarize` with durations from the
  monotonic clock, state `completed_local` then `pending_upload`, upload enqueued, summary screen.
- Recover: reopens the capture as `paused` with a synthetic pause starting at the last stored sample; the metrics are rebuilt from
  the stored samples.

All of the above is **[built]** (compiles, lint has no errors) and **[unverified]** on hardware. Lifecycle, metrics and upload logic
underneath are **[tested: JVM]**.

## Ghost runner (`running/ghost/`)

Atlas prepares, the phone races. A prepared run may carry a route and a ghost (a concrete earlier run on that route, resolved by the
server when the run is prepared: latest, fastest or a chosen run). No part of the race needs the server once the data is on the phone.

**Download.** `Refresh from Atlas` stores the prepared runs (now with `route_id` and `ghost_run_id`) and, for those with a ghost,
downloads `GET /native/routes/{route_id}` (reference path `[[lat, lon, cumulative_m], ...]`) and
`GET /native/runs/{ghost_run_id}/ghost-profile` (points `[moving_t_s, progress_m, hr_bpm|null]`) into `GhostCache` (JSON files in
`noBackupFilesDir/ghost/`, not backed up, ids validated as UUIDs). The prepared list shows `Ghost ready (works offline)` or, if the data
is missing, a warning; Start still works and then runs without the ghost. The cache also checks that route and profile share the same
`geometry_version`.

**Definitions** (identical to `backend/ghost.py`):
- progress = metres along the reference route (not GPS-travelled distance); time = moving time, manual pauses removed for both runners.
- `timeGapS = myT - ghostT(at my progress)`, negative = ahead, shown as `0:23 AHEAD` / `BEHIND`; `leadM = myS - ghostS(at my time)`,
  positive = ahead. Ghost heart rate is shown at my position and at my time next to mine; missing values are shown as a dash.
- A finished ghost stays at the finish line; the screen says so.

**Route matching** (`ProgressTracker`): each usable fix (accuracy <= 30 m, not inside a pause) is projected onto the path inside a
progress window `[last - 25 m, last + 12 m/s * dt + 40 m]` (first fix: within 250 m of the start); progress never decreases; a fix more
than 50 m from the path is not matched. The window is clipped per segment, so a fix far ahead on a long segment is rejected, never
snapped to the window edge. Live-only rules: three unmatched fixes in a row suspend the comparison (`Off the route: comparison
paused`), 10 s without a fix show `GPS lost`, before the first match the screen says `Go to the start of the route`. The numbers shown
are those of the last matched fix, so they are at most about a second old.

**Recovery.** A recovered run rebuilds its ghost race by replaying the stored fixes through the same engine. Runs started from a
prepared run keep `route_id` / `ghost_run_id` in `RunMeta`; after upload the server links the run to the route and computes its own
ghost profile, so every route run becomes a possible future ghost.

| Piece | Status |
|---|---|
| Comparison vs `ghost_golden.json` (Python reference), flat sections, null handling | [tested: JVM] |
| Route progress vs `ghost_progress_golden.json` (noise, 8 s detour, 30 s pause): same profile, matched and off-course counts as Python | [tested: JVM] |
| Session: waiting -> comparing -> off course -> resumes -> GPS lost; pause removes time for both runners; poor accuracy ignored | [tested: JVM] |
| `GhostCache` round trip, readiness, version mismatch, corrupt file, path safety | [tested: JVM] |
| `AtlasClient` route/profile download, prepared-run ids, older server answers | [tested: JVM] |
| Ghost panel on the recording screen, readiness text on the Home screen, replay on recover | [built], [unverified] on hardware |
| Real ghost race against your Polar run on Stadtpark Small | [unverified] |

Known limits: matching assumes one pass over the route in order (loops and out-and-back are handled by the continuity window; routes
that revisit the same place several times can still confuse it); a long GPS gap longer than the window allows suspends the
comparison until a fix fits again; the profile has one point per second of the ghost run.

## Unverified: hardware, Tailscale, outdoor (acceptance boxes left unchecked)

Do not mark any of these passed unless performed on the real phone.

- [ ] Draft section 3 gate: one real >= 20 min outdoor capture with the screen locked, recorded in `MobilePlatform_API.md`, **before** the Running Screen is declared done.
- [ ] Pair the phone; revoke on the web; phone shows re-pair; pair again.
- [ ] Prepared run downloads; Free Run works with Atlas unreachable.
- [ ] 20-minute outdoor run with Polar H10, screen locked part of the time.
- [ ] Temporary Bluetooth loss: run keeps recording, the HR gap stays a gap.
- [ ] Finish offline gives "Pending sync"; reconnect Tailscale gives "Synced"; counts match.
- [ ] Re-sending an upload creates no duplicates.
- [ ] Run visible in RunningTracker History with charts.
- [ ] Process kill during a run: Recover/Discard is offered and nothing is finalized automatically.
- [ ] TWA launcher, Google login and notifications unchanged.
- [ ] QR scan with the Google code scanner.
- [ ] Tailnet: `tailscale serve` mount (path-limited, Funnel off), HTTPS certificate trusted by the phone, public Cloudflare name answers 404 for `/api/runningtracker/native/*` (the shell proxy part is verified by automated tests: 404).
- [ ] Ghost race: prepare a run on Stadtpark Small with ghost "fastest" in Atlas, refresh on the phone (Ghost ready), go offline, run it, finish, sync; the new run appears as a ghost candidate.
- [ ] Sprint02: Finish Run with an H10 -> recovery screen (HR60/HR120 appear at about 60 s / 120 s, reminder after 15 min) -> Finish Training -> recap; also a run without H10 (plain Finish), kill during recovery (Recover/Discard), H10 off for 30 s during recovery, and server samples show no location after the run end.
- [ ] Optional spike (draft section 6): `intent://` "Start Run" from the TWA. **Not built in this sprint**; if built later it must be an activity-alias accepting only a short id matching the prepared-run alphabet and only pre-selecting a prepared run. Result: none (not attempted).

## Test results (automated, development host)

`JAVA_HOME=~/toolchain/jdk17 ANDROID_HOME=~/toolchain/android-sdk bash ./gradlew :app:assembleDebug :app:testDebugUnitTest`:
72 tests, 0 failures (30 Sprint 01 unchanged + 32 running + 10 ghost: engine and parity 8, client 2). `:app:lintDebug`: no errors.

Sprint02 (RunningTracker run finish and recovery) JVM run: `:app:testDebugUnitTest` 115 tests, 0 failures (adds HrSmoothing, RecoveryMetrics/Tracker with the shared golden file, FinishStanding, RecapBuilder, RunMeta compatibility, lifecycle and finish-body tests).

## Sprint03 additions (cadence, metronome, live racing)

Design of record: `03_Application/RunningTracker/Sprint03_CadenceAndLiveRacing/10_architecture.json` (S1, CAD1, CAD2, GB1, MET1, RC1, REL1, C2).

- Upload: step samples ride the existing `PUT /samples` with stream `step`. `expected_counts.step` is sent only when > 0 (omitted, never 0/null). Deploy order (C2): the server must be deployed before a phone build that uploads steps.
- Ghost profile: `GET /native/runs/{id}/ghost-profile` gains `cadence_by_progress` (`[[bucket_start_m, spm], ...]`, 20 m buckets, or null). `GhostProfile.cadenceByProgress` decodes missing/null as "no cadence recorded for this ghost"; nothing is derived from speed.
- Cadence: `CadenceEstimator` (CAD1) mirrors `backend/cadence.py`, parity through `tests/fixtures/cadence_golden.json`. The phone uses it for the live "you N" display only; the server value is stored and authoritative.
- Metronome: `MetronomeMode` OFF / MATCH_GHOST / ATTACK_102 / MANUAL, `MetronomeController` (1 Hz tick -> `TargetSmoother` -> `ClickEngine`), notification action "Click: <mode>" calls the same `cycleMode`. Settings keys in `atlas_run_settings`: `metronome_mode`, `manual_cadence_spm`, `click_volume`. The click stops at Finish Run, Finish and Discard (not kept during recovery).
- Race screen: lower area = `RaceGapPanel` (gap, gaining/losing arrow, gap history, 20 s pace next to the ghost's pace on the same section) | existing `HrDistanceChart`. `MetronomeChip` on the race screen and in the free-run cockpit.
- Permission flow: starting a run asks LOCATION, then ACTIVITY_RECOGNITION once at first use (the run starts whatever the answer); a denial shows "Cadence is not recorded (activity permission denied)" on the home panel.
- Status: pure logic, storage, client mapping `[tested: JVM]`; Compose screens `[built]`; sensor, audio, notification action, screen-off behavior `[unverified]` until a real run.

## Sprint04 additions (Ghost Coach: live coaching)

Design of record: `03_Application/RunningTracker/Sprint04_GhostCoach/10_architecture.json` (COACH1, COACH2, COACH3, SPEECH1, REL2, C3). Package `running/coach/`. Status tags: `[tested: JVM]`, `[built]`, `[unverified]`.

- Plan transport (COACH3): `AtlasClient.nextCoachPlan()` = `GET /native/coach/next-plan` -> `NextPlan(planId, schemaVersion, planJson)` (all null = no active plan). `CoachController.refreshPlan(client)` (blocking, IO; Run home panel only, never during a run) saves the plan in `CoachPlanStore` (SharedPreferences `atlas_coach`: `plan_id`, `plan_json`, `fetched_at`), clears it on a null plan and keeps it on any error. `parseCoachPlan` returns Ok / Unsupported (`schema_version != 1`, shown as "Plan needs an app update") / Invalid; parity with the server through `tests/fixtures/coach_plan_golden.json`. `[tested: JVM]`
- Run link: `RunMeta.coachPlanId` (additive, old metas decode as null) is set when a run starts with 'Coach this run' on and a supported cached plan; `AtlasClient.finish` sends `coach_plan_id` only when set (omitted, never null). **Deploy order (C3): the server must be deployed before a phone build that sends `coach_plan_id`.** `[tested: JVM]`
- Engine (COACH1): pure `CoachEngine.step(plan, state, input, settings)`; no clock, no Android; time is `CoachInput.activeS` = `LiveMetrics.movingS` (elapsed minus pauses; standing still keeps the plan running, OQ2). Constants only in `CoachConfig` (OQ3: first guesses, tune after real sessions). The per-kind cooldown is part of candidate eligibility so a kind that just spoke does not starve the next priority. `[tested: JVM]` (`CoachEngineTest`)
- Session (`CoachController`): `begin` at start/recover (a recovered run resumes at the active time of the interrupted pause, no replayed announcements), `tick` inside the 1 Hz publish OUTSIDE the RunController lock (REL2), `end` at Finish Run / Finish / Discard. Speech failure or unavailability = text only; any other exception disables coaching for the session and is logged; nothing reaches recording, upload or the metronome engine. `[tested: JVM]`
- Metronome (COACH2): `MetronomeMode.COACH` is offered only while a coach session with a cadence target is active (then the ghost modes are not offered); its raw target is the midpoint of the current segment's cadence range, none (silence) otherwise; never persisted (`parse("COACH")` = OFF). `[tested: JVM]`
- Settings: `atlas_run_settings` keys `coach_enabled` (default true), `coach_frequency` (LOW / NORMAL / HIGH, default NORMAL); mute is session-only.
- UI: `CoachPlanCard` on the Run home panel (cached plan, 'Coach this run', frequency, refresh), `CoachStrip` on the ghost race screen and the free-run cockpit layout (last instruction for `DISPLAY_S` seconds, segment and remaining time, mute). `[built]`
- Unverified until a real run: TTS audio, ducking, headphone routing, screen-off coaching, the strip on device, instruction wording and spacing, and the full lifecycle (analyse, accept, coach, next analysis).
