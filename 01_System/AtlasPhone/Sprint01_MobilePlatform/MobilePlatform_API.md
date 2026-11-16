# AtlasPhone Mobile Platform — API, payloads, lifecycle

Code: `01_System/AtlasPhone/app/src/main/java/net/linspad/atlasphone/mobile/`. Status of every statement below is
marked **[tested: JVM]** (automated), **[built]** (compiles, lint clean, NOT run on hardware) or **[unverified]**.
Hardware behaviour is verified only after the physical-device test (see "Test results").

## Entry point

```kotlin
val platform = MobilePlatform.get(context)   // process-wide singleton, independent of any Activity
platform.permissions   // PermissionManager
platform.location      // LocationTracker
platform.heartRate     // HeartRateMonitor
platform.store         // CaptureStore  (durable buffer)
platform.recorder      // CaptureRecorder
platform.eventLog      // StateFlow<List<String>>  errors / reconnect events, newest first
platform.ensureForegroundService(context)   // call from a user action after starting something
platform.stopAll()
```

## Permissions (`permissions/`)

`Capability { LOCATION, BLUETOOTH }`, `PermissionStatus { GRANTED, NOT_REQUESTED, DENIED, BLOCKED }`.
- `status(capability, activity)`, `isGranted`, `toRequest(capability)`, `markRequested(capability)`.
- LOCATION needs precise (`ACCESS_FINE_LOCATION`; coarse is requested alongside as Android 12+ requires, but approximate-only counts as not granted).
- BLUETOOTH needs `BLUETOOTH_SCAN` + `BLUETOOTH_CONNECT` on Android 12+; below, fine location (BLE scan requirement).
- Policy: requested only when the user first uses the capability; after a denial no automatic re-prompt, only an explicit
  "Grant"; BLOCKED ("don't ask again") points to system settings. No background-location permission is requested. **[tested: JVM logic]**
- Showing the system dialog needs an Activity; the diagnostic screen does it (`MobileTestActivity.withPermission`). Another
  screen (RunningTracker) can reuse the same pattern.

## Location (`location/`)

```kotlin
platform.location.start(): Boolean      // false + state explains why
platform.location.stop()
platform.location.state: StateFlow<TrackingState>   // IDLE, TRACKING, SIGNAL_LOST, SERVICES_DISABLED, NO_PERMISSION, ERROR
platform.location.samples: SharedFlow<RawLocation>  // subscribe here
platform.location.latest, .received
```
Fused Location Provider, `PRIORITY_HIGH_ACCURACY`, 1000 ms interval (min 500 ms) while tracking; `removeLocationUpdates` on stop.
`RawLocation(timestampMillis, latitude, longitude, accuracyMeters?, speedMetersPerSecond?, altitudeMeters?, bearingDegrees?)`;
unavailable values are null (never 0). Mapping **[tested: JVM]**, provider behaviour **[built]**.

## Heart rate (`heartrate/`)

```kotlin
platform.heartRate.scan(); stopScan()               // auto-stops after 20 s
platform.heartRate.devices: StateFlow<List<Device>> // address, name, rssi
platform.heartRate.connect(device) / connect(address) / connectLast() / reconnect() / disconnect()
platform.heartRate.state: StateFlow<State>   // IDLE, SCANNING, CONNECTING, CONNECTED, RECONNECTING, DISCONNECTED,
                                             // BLUETOOTH_OFF, NO_PERMISSION, UNAVAILABLE, ERROR
platform.heartRate.samples: SharedFlow<RawHeartRate>   // bpm, timestampMillis (arrival), rrIntervalsMs?
```
Standard Heart Rate Service `0x180D` / Measurement `0x2A37` (any compliant sensor; Polar H10 first). No vendor SDK.
8/16-bit values, RR intervals (converted from 1/1024 s to ms) and sensor-contact flags parsed **[tested: JVM]**. A reading of 0 bpm
is dropped, not reported. The last connected sensor is remembered (SharedPreferences) for "Connect last".
Link loss: up to 5 reconnect attempts with 1/2/4/8/16 s back-off (`ReconnectPolicy` **[tested: JVM]**), then DISCONNECTED until
`reconnect()`. Bluetooth switched off -> BLUETOOTH_OFF, resumes automatically when it returns. BLE flow itself **[built]**.

## Capture buffer (`capture/`)

```kotlin
val id = platform.recorder.start(captureId = null)    // generates a UUID, or continues an existing/interrupted capture
platform.recorder.stop()
platform.recorder.active: StateFlow<CaptureInfo?>

platform.store.fetch(captureId, afterSequence = 0, limit = 1000): List<CaptureSample>   // cursor, no duplicates
platform.store.ack(captureId, upToSequence)           // "safely transferred"
platform.store.purgeAcked(captureId)                  // deletes acknowledged samples only
platform.store.deleteCapture(captureId, force = false) // refuses while unacknowledged samples exist
platform.store.info(id) / list() / openCaptures()
```
SQLite (`mobile_captures.db`). **[tested: JVM, real SQLite via Robolectric]**:
- one `sequence` per capture, shared by both streams, assigned in the insert transaction (unique, strictly increasing,
  continues after a restart);
- committed samples survive closing/reopening the database (process death); `openCaptures()` lists unfinished ones and
  `recorder.start(id)` continues them;
- unacknowledged samples are never deleted automatically; the limit is 100 000 unacknowledged samples per capture, beyond which
  new samples are refused and counted in `dropped` (old data is kept); acknowledging frees room.
The buffer is temporary device infrastructure. Uploading and permanent storage belong to the RunningTracker sprint.

## Payloads (`model/SampleJson`)

```json
{"type":"location.sample","captureId":"uuid","sequence":123,"timestamp":"2026-11-07T10:30:15.000Z",
 "latitude":53.5753,"longitude":10.0153,"accuracyMeters":4.2,"speedMetersPerSecond":2.1,
 "altitudeMeters":18.4,"bearingDegrees":92.0}
{"type":"heartRate.sample","captureId":"uuid","sequence":124,"timestamp":"2026-11-07T10:30:15.000Z",
 "bpm":152,"rrIntervalsMs":[400,410],"source":"bluetooth"}
```
Units: degrees, metres, metres/second, milliseconds. Timestamps are ISO-8601 UTC with milliseconds: for location the fix's own time
(arrival time if the provider gave none), for heart rate the moment the notification arrived on the phone. Streams keep their own
timestamps and do not arrive simultaneously. Unavailable values are `null`. **[tested: JVM]**

## How a new app subscribes (RunningTracker later)

```kotlin
val p = MobilePlatform.get(context)
p.permissions.status(Capability.LOCATION, activity)          // then request via the Activity pattern
p.location.start(); p.heartRate.connectLast()
lifecycleScope.launch { p.location.samples.collect { /* RawLocation */ } }
lifecycleScope.launch { p.heartRate.samples.collect { /* RawHeartRate */ } }
val id = p.recorder.start()                                   // optional: buffer both streams durably
p.ensureForegroundService(context)
// later: p.store.fetch(id, cursor) -> upload -> p.store.ack(id, lastSeq) -> p.store.purgeAcked(id)
```
Distance, pace, routes and ghost logic stay in the app; the platform only delivers samples.

## Foreground service (`service/RecordingService`)

Started by `ensureForegroundService` from a user action; types `location|connectedDevice` (only those whose permissions are
granted); persistent notification "AtlasPhone is recording sensors" with a Stop action; partial wake lock (max 4 h) while it runs;
stops itself 3 s after GPS, sensor and capture are all inactive. It owns no sensors. **[built]**, screen-off behaviour **[unverified]**.

## Behaviour when AtlasPhone is closed, minimised or the screen is locked

| Situation | Expected | Status |
|---|---|---|
| Screen on, diagnostic screen open | all modules run; screen kept awake | [unverified] |
| App minimised / screen locked while recording | foreground service keeps process, GPS and BLE alive; samples keep being buffered | [unverified] |
| User swipes the app away | foreground service may be stopped by the system; buffered samples remain; capture shows as interrupted and can be continued | [unverified] (buffer durability [tested: JVM]) |
| Process killed | sensors are NOT restarted automatically (`START_NOT_STICKY`); committed samples remain | [tested: JVM] for storage |
| Android battery optimisation (OEM) | may still restrict background work; exempt AtlasPhone if gaps show up | [unverified] |

## Not part of this sprint

Server upload/download (next sprint, over Tailscale), routes, runs, ghost logic, maps, web bridge (removed, see
00_draft.md "Why the sprint changed").

## Test results

Automated (JVM, `./gradlew :app:testDebugUnitTest`): 30 tests — heart-rate parser, reconnect policy, permission logic,
location mapping, capture store + recorder (Robolectric/SQLite), retrieval verification. Lint (`:app:lintDebug`): no errors.

Physical device (Android phone, Polar H10), 2026-11-08, reported by the user as "everything works" (not itemised):
GPS start/stop and live values, H10 scan/connect/live BPM, capture and buffer checks from the diagnostic screen.
- **Not run on the device:** permission denial / "don't ask again" flow (user chose to defer; logic is unit-tested, dialog flow unverified).
- **Not confirmed:** the 20-minute outdoor run and the screen-locked run (foreground service), Bluetooth drop/reconnect, and
  reload/process-death behaviour. Treat the foreground-service and reconnection rows above as [unverified] until reported.
Checklist is the acceptance list in `00_draft.md`.

## Sprint 02 additions (additive; see Sprint02_RunningScreen/RunningScreen_API.md)

- `RawLocation` and `RawHeartRate` gained `elapsedRealtimeNanos: Long? = null` (monotonic stamp); `SampleJson` emits it as
  `elapsedRealtimeNanos` (null when absent). Existing captures and callers are unaffected. **[tested: JVM]**
- `CaptureStore` is database version 2 and adds `putRunMeta/getRunMeta/listRunMeta/deleteRunMeta` (table `run_meta`);
  `deleteCapture` also removes the run's metadata. Version-1 databases upgrade in place. **[tested: JVM]**
- The 20-minute locked-screen hardware capture required by the RunningTracker sprint is still open; record it here when done.

## Sprint03 additions (cadence, click, quick action)

Status tags: `[tested: JVM]` pure logic and storage, `[built]` compiles, `[unverified]` needs a real run.

- `platform.steps: StepDetector` - `samples: Flow<RawStep>`, `state` (STOPPED / LISTENING / NO_SENSOR / NO_PERMISSION), `start(): Boolean`, `stop()` (flush, then unregister). Android `TYPE_STEP_DETECTOR`, batching allowed (`STEP_MAX_REPORT_LATENCY_MS`); `RawStep.timestampMillis` is the sensor EVENT time converted to UTC (`StepDetector.toRaw`) `[tested: JVM]`. Sensor callbacks only `tryEmit` into a buffered flow (oldest dropped when full). Sensor, batching and screen-off delivery `[unverified]`.
- `platform.click: ClickEngine` (implements `ClickOutput`) - streaming `AudioTrack` on its own thread, `BeatScheduler` for sample-accurate beats `[tested: JVM]`, `setTargetSpm` / `setVolume` are atomics, no audio focus is requested (mixes with other audio). Audio output, mixing, route changes `[unverified]`.
- `platform.quickAction: QuickAction` - one app-supplied notification action (`set(label, handler)`); `RecordingService` renders it as a second action (`ACTION_QUICK`) `[built]`.
- `Stream.STEP` (payload `step.sample`, HTTP stream name `step`, `Stream.apiName`); `SampleJson.step` `[tested: JVM]`.
- `CaptureStore` SQLite version 3: `captures.step_count`; the sequence stays one counter shared by all streams `[tested: JVM]`. `CaptureInfo.stepCount`.
- Permission `ACTIVITY_RECOGNITION` (`Capability.ACTIVITY_RECOGNITION`): required from Android 10, none before (counts as granted) `[tested: JVM]`.
- `stopAll()` also stops steps and click and clears the quick action.

## Sprint04 additions (speech output)

Status tags: `[tested: JVM]` pure logic, `[built]` compiles, `[unverified]` needs a real run.

- `platform.speech: SpeechOutput` (implements `SpeechPort`) - speaks a string through the system `TextToSpeech`. Domain-free: it knows nothing about running. `state`: IDLE / READY / UNAVAILABLE (engine init failed or English not supported). `prepare()` starts the engine in the background (idempotent), `speak(text): Boolean` is queue-flush and returns false when UNAVAILABLE or not yet initialised (the caller shows the text only), `stop()` stops speaking, abandons focus and releases the engine (idempotent; `MobilePlatform.stopAll()` calls it). Nothing throws and nothing blocks the caller. The `SpeechPort` seam is `[tested: JVM]` through the coach session tests; the engine itself is `[built]`.
- Audio focus (SPEECH1): utterances use `USAGE_ASSISTANCE_NAVIGATION_GUIDANCE` and request `AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK` around each utterance (abandoned on done/error) so music ducks briefly. This is a scoped exception to the "no audio focus" rule, which continues to apply to `ClickEngine` only. Real TTS audio, ducking, headphone routing and screen-off speech are `[unverified]` until a real run.
