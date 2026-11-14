# Test Spec — RunningTracker — Sprint02_RunFinishAndRecovery

## Scope
Automated: server API and metrics (pytest in `atlas-runningtracker-test`, `make -C 01_System test-run COMPONENT=runningtracker`), the web Recovery card with stubbed API (Playwright), and phone pure logic (JVM: `JAVA_HOME=~/toolchain/jdk17 ANDROID_HOME=~/toolchain/android-sdk bash ./gradlew :app:testDebugUnitTest` in `01_System/AtlasPhone`; the existing Sprint01/ghost JVM tests must still pass). Marked `[Phone JVM]` = automated JVM test of pure phone code. Marked `[UI — manual]` = Compose screens and hardware behavior (physical phone, Polar H10, locked screen, process kill, Tailscale): no automation exists, the test report must list them as untested, never as passing. Out of scope: roadmap Sprint 2-4 features, backfilling recovery for old runs.

Fixture names (added to `tests/fixtures.sql`, ids prefixed `fix-`; existing fixtures stay): `fix-run-complete` (legacy, `run_finished_at` NULL, metrics `algo_version` 1), `fix-run-recovery` (complete; running 0-600 s, recovery to 900 s; HR samples incl. a spike at running end and a gap; metrics with a recovery object), `fix-run-recovery-nohr` (complete, `run_finished_at` set, no heart-rate samples), `fix-run-recovery-upload` (uploading, samples after the run end already stored, finish not yet called), device `fix-device-1`. Shared oracle: `tests/fixtures/recovery_golden.json` (pytest and Kotlin read the same file).

## Scenarios

### Finish with run end stores it and clips running statistics
- **Given:** `fix-run-recovery-upload` with all samples stored (running phase GPS + HR, recovery-phase HR) and `fix-device-1`
- **When:** the phone calls finish with `finished_at`, `run_finished_at` inside the run, matching expected counts and last seq
- **Then:** result is `complete`; the run stores `run_finished_at`; avg HR, max HR, HR series, split average HR, distance and pace are computed only from samples at or before `run_finished_at`; the recovery-phase HR samples remain stored and counted in `verified_counts`

### Finish without run end behaves as before
- **Given:** an uploading run with all samples stored
- **When:** finish is called without `run_finished_at` (old phone build)
- **Then:** result is `complete`; `run_finished_at` stays empty; nothing is clipped; the recovery Dataset for the run is empty; no recovery object is stored

### Run end before the start is rejected
- **Given:** `fix-run-recovery-upload`
- **When:** finish is called with `run_finished_at` earlier than the run's `started_at`
- **Then:** 422 `VALIDATION_ERROR` in the ApiError envelope; the run stays `uploading` and nothing was changed

### Run end after the training end is rejected
- **Given:** `fix-run-recovery-upload`
- **When:** finish is called with `run_finished_at` later than `finished_at`
- **Then:** 422 `VALIDATION_ERROR` in the ApiError envelope; nothing was changed

### Repeated finish of a complete run keeps the stored run end
- **Given:** `fix-run-recovery` (complete)
- **When:** finish is called again, once identically and once with a different `run_finished_at`
- **Then:** both answer `complete` with the same verified counts; the stored `run_finished_at` and `finished_at` are unchanged; metrics are not altered

### Replay recomputes a legacy run without inventing recovery
- **Given:** `fix-run-complete` whose metrics carry the old algorithm version
- **When:** finish is replayed for it
- **Then:** its metrics are recomputed and now carry the new algorithm version; distance, splits, avg/max HR and series equal the previous values; its recovery stays empty

### Old phone body is still accepted, unknown keys still are not
- **Given:** `fix-device-1` and an uploading run
- **When:** finish is sent once without the new field and once with an unrelated unknown key
- **Then:** the first is accepted; the second returns 422 `VALIDATION_ERROR`

### HRR values are computed from the end of running
- **Given:** `fix-run-recovery` HR samples per the golden vector (end HR around the run end, readings around +60 s and +120 s)
- **When:** finish metrics are computed (or the run is recomputed)
- **Then:** `hr_end`, `hr_60`, `hr_120` equal the golden values (median of valid readings in the declared windows) and `hrr60` = `hr_end` − `hr_60`, `hrr120` = `hr_end` − `hr_120` within 0.01 bpm

### Recovery values are empty, not zero, when not computable
- **Given:** golden vectors with fewer than two valid readings around +60 s, and a vector where training ended 61 s after the run end
- **When:** recovery is computed
- **Then:** the affected `hr_60` / `hr_120` and the `hrr` values derived from them are null; the other values that are computable are still returned; no value is 0

### Artifacts are ignored, raw samples stay
- **Given:** golden vectors with a 0 bpm reading, a 250 bpm reading, and a single isolated spike between two normal readings; also a genuine step change that stays at the new level
- **When:** recovery is computed
- **Then:** the 0, the 250 and the isolated spike do not influence any recovery value or the curve; the genuine step change is kept; all of those samples are still present unmodified in the stored raw samples

### Recovery curve covers the recovery phase without zero-filling
- **Given:** `fix-run-recovery` with a heart-rate gap of about 20 s inside the recovery phase
- **When:** the recovery series is requested
- **Then:** points start at 0 s (end of running) and run until the training end in 5-second steps, ordered by time ascending; steps inside the gap are absent (no zero, no interpolation)

### Run without heart rate has an empty recovery
- **Given:** `fix-run-recovery-nohr`
- **When:** the recovery Dataset and the recovery series are requested
- **Then:** the recovery Dataset has one row whose HR and HRR values are null and whose recovery duration equals finished minus run end; the recovery series is an empty Dataset (total 0)

### Recovery Dataset for a run with recovery
- **Given:** `fix-run-recovery`
- **When:** `GET /api/runningtracker/runs/{id}/recovery`
- **Then:** a single-row Dataset (object type `run_recovery`) with `run_finished_at`, `recovery_s`, `hr_end`, `hr_60`, `hr_120`, `hrr60`, `hrr120`, no pagination beyond one row

### Recovery Dataset is empty for legacy and uploading runs, 404 for unknown
- **Given:** `fix-run-complete` (legacy), `fix-run-recovery-upload` (uploading) and an unknown run id
- **When:** the recovery endpoint is requested for each
- **Then:** the first two return an empty Dataset with total 0; the unknown id returns 404 `NOT_FOUND` ApiError

### Series metric validation
- **Given:** `fix-run-recovery`
- **When:** the series endpoint is requested with metric `recovery_hr`, `heart_rate`, `pace`, and with an unsupported metric or none
- **Then:** the three supported metrics return Datasets (the `heart_rate` series ends at the run end and contains no recovery readings); the unsupported or missing metric returns 422

### History averages exclude recovery
- **Given:** `fix-run-recovery` and `fix-run-complete`
- **When:** the runs list and the run detail row are requested
- **Then:** the average and max HR of `fix-run-recovery` are the running-phase values; `fix-run-complete` rows are unchanged from Sprint01

### Deleting a run removes its recovery data
- **Given:** `fix-run-recovery`
- **When:** the run is deleted
- **Then:** its metrics (including recovery) and samples are gone and the recovery endpoint returns 404

### [Phone JVM] Lifecycle supports the recovery phase
- **Given:** the lifecycle state machine
- **When:** `FINISH_RUN` is applied in RECORDING and PAUSED, `FINISH_TRAINING` in RECOVERY, `RECOVER` in RECOVERY, and every other state/event combination is swept
- **Then:** FINISH_RUN leads to RECOVERY, FINISH_TRAINING to COMPLETED_LOCAL, RECOVER keeps RECOVERY; the legacy FINISH path (RECORDING|PAUSED → COMPLETED_LOCAL) and all old transitions are unchanged; every other combination (including FINISH_RUN from RECOVERY, FINISH_TRAINING from RECORDING, FINISH_RUN from SYNCED) is illegal; the full path RECORDING → RECOVERY → COMPLETED_LOCAL → PENDING_UPLOAD → SYNCED works

### [Phone JVM] No H10 skips recovery
- **Given:** the recovery gate
- **When:** asked with a live heart-rate reading and with none
- **Then:** with a reading it offers Finish Run; without one it offers plain Finish (no recovery phase, run end stays empty)

### [Phone JVM] Smoothing never turns missing into zero
- **Given:** a heart-rate series with a 0 bpm reading, an out-of-range reading, an isolated spike, and a 12 s gap
- **When:** smoothed with Raw, 5 s and 10 s windows
- **Then:** those positions yield gaps (null), never 0; the windows at the edges use only available valid readings; trailing and centered windows differ only by window placement; raw values are unchanged

### [Phone JVM] Phone and server agree on recovery values
- **Given:** `tests/fixtures/recovery_golden.json`
- **When:** the Kotlin recovery computation and the Kotlin validity rule are run on every vector
- **Then:** values equal the golden expectations (same file the server tests use) within 0.01 bpm

### [Phone JVM] Summary excludes the recovery segment
- **Given:** a run with GPS samples only during running and heart-rate samples continuing 3 minutes after the run end
- **When:** the run summary and the recap data are built at the run end and at training end
- **Then:** distance, running time, average pace, average HR, max HR and splits equal the values computed from running samples only; the recap HR series covers both phases; the running summary is not recomputed at training end

### [Phone JVM] Final standing and achievements from real data only
- **Given:** a route with a field of cached ghost profiles including a main ghost and a most recent run
- **When:** the standing is computed for a completed route (faster than all, between ghosts, slower than all, tie with a ghost) and for an incomplete route
- **Then:** position, overtaken count, rival beaten and margin follow the declared rules; personal record is true only when the run is completed, the field is non-empty and the position is 1 (ties favor the runner, so a tie with the fastest ghost still gives a personal record, per ST1); beat-previous is true only when the previous run's profile is cached and slower; with no matched fix or no ghost the standing is absent; the field ranking function itself is unchanged

### [Phone JVM] Old run metadata still decodes
- **Given:** a stored run metadata JSON written before this sprint (no run end, recovery or recap keys) and one with the new keys
- **When:** decoded and re-encoded
- **Then:** the old one decodes with those values absent and keeps working through upload; the new one round-trips unchanged; the smoothing setting defaults to the 5-second window when unset or unknown

### [Phone JVM] Finish request carries the run end only when set
- **Given:** a pending-upload run with and without a run end
- **When:** the finish request body is built
- **Then:** the body contains `run_finished_at` (ISO-8601 UTC) only for the run with a run end; it is omitted, not null, otherwise

### [Phone JVM] Recovery tracker and reminder
- **Given:** a tracker created at the run end with the last readings before it and a stream of readings afterwards
- **When:** snapshots are taken at 30 s, 65 s, 125 s and after 15 minutes
- **Then:** HR60 appears only once its window is complete, HR120 later; HRR values follow; the reminder flag becomes true only after 15 minutes; missing readings never appear as 0

### [UI] Web run detail shows the Recovery card
- **Given:** the run detail page with stubbed responses: a recovery Dataset row (end 172, 60 s 150, 120 s 138 bpm), a recovery series, and the other existing responses
- **When:** the page is opened
- **Then:** a Recovery card shows HRR60 22 and HRR120 34 as whole bpm drops, the end/60 s/120 s values, the recovery heart-rate chart, and the text that HRR is the drop after exercise and not the return to resting heart rate; the existing pace and heart-rate charts, splits and comment are still shown

### [UI] Web run detail hides the Recovery card without recovery
- **Given:** stubbed responses where the recovery Dataset is empty (legacy run)
- **When:** the page is opened
- **Then:** no Recovery card is rendered and no error is shown; a null HRR value (for example only HR end available) is shown as a dash, never 0

### [UI — manual] Finish Run starts the recovery screen
- **Given:** a paired phone with an H10 connected, a running recording (free run and a ghost race)
- **When:** the user taps Finish Run and confirms
- **Then:** the timer, distance and GPS stop at that moment, the recovery screen appears with smoothed HR, time since run end and a growing HR graph; HR60 and HR120 tiles fill in at about 60 s and 120 s; consistency guidance is visible; a reminder appears after about 15 minutes; nothing saves automatically

### [UI — manual] Finish Training shows the recap
- **Given:** the recovery screen after at least 2 minutes
- **When:** the user taps Finish Training and confirms
- **Then:** the recap shows primary results (distance, running time, average pace, position n/N, ghosts overtaken, rival result) larger than secondary results (HR profile, average/max HR, HRR60/HRR120, pace evolution, ghost comparison); only real achievements appear; there is no animation or pop-up; sync status and retry are shown; airplane mode does not change the content

### [UI — manual] Run without H10 finishes directly
- **Given:** a running recording without a heart-rate reading
- **When:** the user taps Finish
- **Then:** no recovery phase starts; the recap appears without HR and HRR blocks (omitted, not zero) and the run syncs normally

### [UI — manual] Kill during recovery
- **Given:** the recovery screen is open
- **When:** the app process is killed and the Running Screen is reopened
- **Then:** the run is offered as Recover or Discard; Recover resumes the recovery screen with the running result intact and HR reconnecting; the run is never finalized automatically

### [UI — manual] H10 disconnect during recovery
- **Given:** the recovery screen with a live HR
- **When:** the H10 is switched off for 30 s and reconnected
- **Then:** the HR graph shows a gap (no zero), the connection state and Reconnect are visible, Finish Training stays available, and HRR values that lack data show a dash

### [UI — manual] GPS stops and heart rate continues at the run end
- **Given:** a real run followed by a 2-minute recovery
- **When:** the run is synced and the raw samples are inspected
- **Then:** no location sample is later than the run end (plus the short drain), heart-rate samples continue until training end, and the run appears in Atlas history with running-only distance, time, pace and averages

### [UI — manual] Smoothing setting
- **Given:** the home panel setting and a live run with HR
- **When:** Raw, 5 s (default) and 10 s are selected
- **Then:** the live HR value and HR graphs, the recovery graph and the recap HR chart follow the selected mode; stored data and the HRR values do not change
