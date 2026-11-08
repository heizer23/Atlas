# Test Spec — RunningTracker — Sprint01_RecordAndSync

## Scope
Automated: backend (pytest in `atlas-runningtracker-test`, `make -C 01_System test-run COMPONENT=runningtracker`), shell proxy, web UI with stubbed API (Playwright), and AtlasPhone JVM tests (`JAVA_HOME=~/toolchain/jdk17 ANDROID_HOME=~/toolchain/android-sdk bash ./gradlew :app:assembleDebug :app:testDebugUnitTest` in `01_System/AtlasPhone`, plus Sprint 01's 30 tests unchanged). Out of scope for automation and reported separately as manual/unverified: physical phone, Tailscale on phone, tailnet TLS, outdoor and Polar H10 runs.

Fixture names: device `fix-device-1` (active, token known to conftest), `fix-device-2` (revoked), prepared runs `fix-prepared-fresh` and `fix-prepared-expired`, complete run `fix-run-complete` (20 samples per stream, one pause, metrics), uploading run `fix-run-gap` (seq 5-8 missing), pairing codes `fix-code-active`, `fix-code-expired`, `fix-code-used`.

## Scenarios

### Pairing creates a device token once
- **Given:** an active pairing code created through the web endpoint
- **When:** the phone redeems it with a device name
- **Then:** the response contains a device id and a token; the code is single use; the database stores only hashes (neither token nor code appear in any column); the web code-creation response is a single-row Dataset with the plain code, expiry about 5 minutes ahead, and native_base_url

### Pairing code cannot be reused
- **Given:** `fix-code-used`
- **When:** it is redeemed
- **Then:** 403 PAIRING_FAILED with the same generic message as for an unknown code

### Expired pairing code is refused
- **Given:** `fix-code-expired`
- **When:** it is redeemed
- **Then:** 403 PAIRING_FAILED, identical body shape to the unknown-code case

### Pairing lockout after five wrong attempts
- **Given:** `fix-code-active` and no prior failures
- **When:** five wrong codes are submitted, then the correct code
- **Then:** the correct code is refused (429 PAIRING_RATE_LIMITED while the window is active), the previously active code stays locked even after the window, and a freshly created code redeems normally once the window has passed

### Revoked token is rejected
- **Given:** a paired device
- **When:** the web Revoke action is called, then any native call is made with that token; Revoke is called a second time
- **Then:** the native call returns 401 DEVICE_UNAUTHORIZED; the second revoke succeeds and keeps the original revoked_at; the device list shows is_revoked true

### Native endpoints require a device token
- **Given:** no Authorization header, a malformed header, an unknown token
- **When:** each native endpoint except pair is called
- **Then:** every call returns 401 DEVICE_UNAUTHORIZED in the ApiError envelope

### Device token has no extra power on web endpoints
- **Given:** a valid device token
- **When:** it is used as Bearer on web paths such as GET /runs
- **Then:** web paths ignore it (behavior identical to no token); the token authorizes only /native routes

### Native route rejected when it arrives through the public path
- **Given:** a native request carrying a CF-Connecting-IP header
- **When:** it reaches the backend
- **Then:** 403 NATIVE_ROUTE_FORBIDDEN

### Shell proxy hides native routes
- **Given:** the full stack with atlas-shell
- **When:** GET /api/runningtracker/runs and then GET and POST /api/runningtracker/native/prepared-runs, /native/pair and a path with doubled slashes are requested through http://atlas-shell
- **Then:** the first returns JSON from the backend; every native request returns 404 and the backend log shows no native request

### Prepared run lifecycle
- **Given:** an empty prepared list
- **When:** the web creates a prepared run with a title, the phone lists and downloads it, then deletes on the web
- **Then:** the create response is a single-row Dataset with a 6-char short_id and expires_at about 48 h ahead; the native list contains it; after deletion the native download returns 404

### Expired prepared run is hidden from the phone
- **Given:** `fix-prepared-expired`
- **When:** the phone lists and downloads prepared runs
- **Then:** it is absent from the list and its download returns 404; the web list still shows it with is_expired true

### Begin is idempotent and returns cursors
- **Given:** a new client-generated run id
- **When:** begin is called twice with the same started_at
- **Then:** one row with status uploading; both responses 200 with high_seq zeros and contiguous_seq 0; a run owned by another non-revoked device answers 404

### Begin on a prepared run converts it
- **Given:** `fix-prepared-fresh`
- **When:** the phone calls begin with that id
- **Then:** the run becomes uploading with the phone's started_at and device_id; calling begin again changes nothing

### Begin adopts a run of a revoked device
- **Given:** an uploading run owned by revoked `fix-device-2`
- **When:** `fix-device-1` calls begin for it
- **Then:** 200 and the run is now owned by `fix-device-1`; for a complete run owned by a revoked device the answer is 404

### Sample upload is idempotent
- **Given:** an uploading run and a batch of 100 location and 30 heart-rate samples with shared increasing seq
- **When:** the same batch is sent twice
- **Then:** first response stored 130 duplicates 0; second stored 0 duplicates 130; row count unchanged; stored payloads are byte-for-byte what was sent (nullable fields still null)

### Duplicate seq with different payload never overwrites raw data
- **Given:** a stored sample at seq 7
- **When:** a batch re-sends seq 7 with a different payload
- **Then:** counted as duplicate, stored payload unchanged

### Batch limit and validation
- **Given:** an uploading run
- **When:** a batch of 2001 samples, a sample with unparsable timestamp, and a seq of 0 are sent separately
- **Then:** each is rejected with 422 and nothing from the rejected batch is stored (atomic)

### Samples rejected for a complete run
- **Given:** `fix-run-complete`
- **When:** a sample batch is sent for it
- **Then:** 409 RUN_NOT_UPLOADABLE

### Resume cursors reflect stored data
- **Given:** `fix-run-gap` (seq 1-4 and 9-20 stored)
- **When:** begin is called and a further batch is uploaded
- **Then:** contiguous_seq is 4 and per-stream high_seq reflects the highest stored seq of each stream

### Finish verifies and completes
- **Given:** an uploading run with all samples uploaded (counts and contiguous seq match)
- **When:** finish is called with matching expected_counts, last_seq and two closed pauses
- **Then:** result complete, verified_counts equal expected, status complete, pauses stored, run_metrics row with algo_version 1; calling finish again returns complete with the same counts and does not duplicate pauses or metrics

### Finish detects gaps
- **Given:** `fix-run-gap`
- **When:** finish is called with last_seq 20 and counts for 20 samples
- **Then:** result incomplete with missing_seq_ranges [5-8], status stays uploading, summary fields are stored; after the missing samples are uploaded a new finish returns complete

### Finish detects count mismatch without gaps
- **Given:** a run whose stored seqs are contiguous but heart_rate expected count is higher than stored
- **When:** finish is called
- **Then:** result incomplete with count_mismatch naming heart_rate and no missing ranges

### Finish rejects inconsistent times
- **Given:** an uploading run
- **When:** finish is called with finished_at before started_at
- **Then:** 422 VALIDATION_ERROR and nothing changes

### GPS-only run completes with empty heart-rate series
- **Given:** a run uploaded with location samples only and expected heart_rate count 0
- **When:** finish is called and the series endpoint is read with metric heart_rate
- **Then:** result complete; avg_hr null; heart_rate series is an empty Dataset (no zeros)

### Ownership on every native call
- **Given:** a run owned by `fix-device-1`, and a second active device
- **When:** the second device calls samples, finish and prepared download for it
- **Then:** 404 NOT_FOUND on each; no data is changed or leaked

### Metrics follow algorithm A1 (golden vectors)
- **Given:** the golden vectors file (clean route, route with pause, GPS jump, low-accuracy fixes, stationary stretch, GPS-only run)
- **When:** metrics are computed
- **Then:** distance within 0.5 m, split durations within 0.5 s, avg/max hr and series match the expected values; fixes inside pauses add nothing; the first fix after a pause adds no distance

### Metrics recompute is stable
- **Given:** `fix-run-complete`
- **When:** metrics are recomputed twice
- **Then:** the stored run_metrics row is identical and raw samples are unchanged

### History list is a Dataset with defined ordering and defaults
- **Given:** fixtures with complete, uploading and prepared runs
- **When:** GET /runs without params, with status=prepared, with page_size=1 page=2, and with page_size=101 or status=bogus
- **Then:** default lists uploading and complete only, newest started_at first; status=prepared lists prepared runs; pagination meta total is the unpaginated count; invalid params return 422 ApiError; an empty result is an empty Dataset with total 0; sync_state is pending for uploading and synced for complete

### Run detail, splits and series
- **Given:** `fix-run-complete`
- **When:** GET /runs/{id}, /splits, /series?metric=pace and metric=heart_rate are read; /series without metric; an unknown id
- **Then:** single-row Dataset with avg_pace_s_per_km derived from moving_s and distance_m; splits ordered by km; series ordered by t_s with x and y numeric; missing metric 422; unknown id 404 ApiError

### Comment PATCH distinguishes omit, value and null
- **Given:** a run with comment "tempo"
- **When:** PATCH with {} ; with {"comment": "easy"} ; with {"comment": null} ; with {"comment": "   "} ; with {"other": 1}
- **Then:** unchanged; "easy"; NULL; NULL; 422

### Delete run removes all derived data
- **Given:** `fix-run-complete`
- **When:** DELETE /runs/{id}
- **Then:** empty Dataset; samples, pauses and metrics are gone; a second delete returns 404

### Devices list and pairing do not expose secrets
- **Given:** paired and revoked devices
- **When:** GET /devices and GET /prepared-runs are read and the application log is inspected
- **Then:** rows contain no token or hash fields; logs contain no tokens, codes or sample payloads

### Schema is idempotent
- **Given:** an initialized schema
- **When:** schema.sql is executed again at startup
- **Then:** no error and no data change

### Native lifecycle transitions (JVM)
- **Given:** the RunLifecycle state machine
- **When:** all events are applied to all states
- **Then:** prepared to recording to paused and back, finish from recording or paused, completed_local to pending_upload to synced are legal; illegal transitions return null; a free run starts at recording; recovery enters paused; RunMeta survives a JSON round trip

### Native metrics match golden vectors (JVM)
- **Given:** the same golden vectors file as the backend
- **When:** RunMetrics runs on them
- **Then:** results equal the backend within the same tolerances; incremental accumulator and batch summarize agree

### Upload resumes from the server cursor (JVM)
- **Given:** a capture with 3000 samples and a fake server whose begin reports contiguous_seq 1200
- **When:** the upload logic runs
- **Then:** the first batch starts at seq 1201; batches never exceed 1000 samples; finish is called after the last batch

### Local samples are acknowledged only after verified finish (JVM)
- **Given:** a fake server that answers finish with incomplete, then complete
- **When:** the upload logic runs
- **Then:** no sample is acked or purged before the complete answer; on the gap answer the next send starts before the first gap; after at most three resend rounds an unresolved mismatch leaves the run pending_upload with a visible error

### Upload error handling (JVM)
- **Given:** fake server answers 401, then network failure, then 404
- **When:** the upload logic handles each
- **Then:** 401 marks needs-repair and stops; network failure schedules a retry and keeps samples; 404 fails visibly; none of them deletes local data

### Token storage never holds plaintext (JVM)
- **Given:** TokenStore with a fake cipher
- **When:** a pairing is saved, read, cleared, and a corrupt blob is read
- **Then:** the preferences file contains no plaintext token; read returns the token; clear removes it; corrupt blob returns null; a non-https base URL is refused

### AtlasClient is https-only and leaks nothing (JVM)
- **Given:** AtlasClient with a fake transport
- **When:** constructed with http://..., and with https calling each endpoint
- **Then:** http is refused; Authorization Bearer is sent on all calls except pair; stream names are mapped to location and heart_rate; error messages and exceptions contain no token

### Sprint 01 behavior unchanged (JVM)
- **Given:** the existing 30 Mobile Platform tests
- **When:** the full unit test task runs after the additive sample-field and CaptureStore version changes
- **Then:** all pass; an existing version-1 capture database upgrades without losing captures or samples

### [UI] History list shows sync state
- **Given:** stubbed GET /runs with one synced and one pending run
- **When:** the user opens Running, then History
- **Then:** rows show date, distance, duration, average pace, average heart rate ("–" when missing) and a clear "Synced" or "Pending sync" label; an empty history shows an empty state

### [UI] Run detail shows charts, splits and comment edit
- **Given:** stubbed detail, splits and series responses, and a run without heart-rate data
- **When:** the user opens a run and clears the comment
- **Then:** pace chart, HR chart (or a "no heart-rate data" note), splits table and no map are shown; clearing the comment sends null in the PATCH body

### [UI] Pair phone shows code, QR and expiry
- **Given:** stubbed POST /pairing-codes
- **When:** the user presses Pair phone on Devices
- **Then:** the code is shown as text with a QR, an expiry countdown, and the code disappears when expired; the device list shows name and last used with Revoke only on active devices

### [UI] Prepared runs on the Run page
- **Given:** stubbed prepared-run endpoints
- **When:** the user creates and deletes a prepared run
- **Then:** the list updates, expired entries are marked, and the page explains that Free Run starts on the phone

## Manual / hardware (UNVERIFIED — cannot be run on the development host; do not mark passed unless performed)

Tailnet, TLS and exposure (operator and phone):
- [ ] [Manual — hardware] `tailscale serve status` shows only the path-limited mount for /api/runningtracker/native on 8443 and funnel is off.
- [ ] [Manual — hardware] From the phone on Tailscale, HTTPS to the tailnet name succeeds with a publicly trusted certificate; from outside the tailnet it is unreachable; GET of a web path (for example /api/runningtracker/runs) on the tailnet name returns 404.
- [ ] [Manual — hardware] Through the public Cloudflare hostname, /api/runningtracker/native/* returns 404.

Physical device acceptance (reported separately from automated results):
- [ ] [Manual — hardware] Pair the phone; revoke on the web; phone shows re-pair; pair again.
- [ ] [Manual — hardware] Prepared run downloads; Free Run works with Atlas unreachable.
- [ ] [Manual — hardware] 20-minute outdoor run with Polar H10, screen locked part of the time (also satisfies the Sprint 01 gate; record result in MobilePlatform_API.md).
- [ ] [Manual — hardware] Temporary Bluetooth loss: run keeps recording, HR gap stays a gap.
- [ ] [Manual — hardware] Finish offline gives pending sync; reconnect Tailscale gives synced; counts match.
- [ ] [Manual — hardware] Re-sending an upload creates no duplicates.
- [ ] [Manual — hardware] Run visible in History with charts.
- [ ] [Manual — hardware] Process kill during a run: Recover/Discard is offered and nothing is finalized automatically.
- [ ] [Manual — hardware] TWA launcher, Google login and notifications unchanged.
- [ ] [Manual — hardware] Optional spike: intent:// "Start Run" from the TWA; result documented in RunningScreen_API.md.
- [ ] [UI — manual] QR scan on the pairing screen with the Google code scanner.
