# Test Spec — RunningTracker — Sprint03_CadenceAndLiveRacing

## Scope
Automated: server API, cadence and ghost-cadence derivation (pytest in `atlas-runningtracker-test`, `make -C 01_System test-run COMPONENT=runningtracker`), the web cadence stat/card with stubbed API (Playwright), and phone pure logic (JVM: `JAVA_HOME=~/toolchain/jdk17 ANDROID_HOME=~/toolchain/android-sdk bash ./gradlew :app:testDebugUnitTest` in `01_System/AtlasPhone`; all existing Sprint01/02 and ghost JVM tests must still pass). Marked `[Phone JVM]` = automated JVM test of pure phone code. Marked `[UI — manual]` = Compose screens, sensors, audio and hardware behavior (physical phone, headphones, locked screen, music app, Polar H10): no automation exists, the test report must list them as untested, never as passing. Out of scope: roadmap Sprint 3-4 features, backfilling cadence for old runs, speaker guard, exhaustive device matrix.

Fixture names (added to `tests/fixtures.sql`, ids prefixed `fix-`; existing fixtures stay): `fix-run-cadence` (complete; running with location, heart-rate and step samples, a metrics cadence object, a qualified route profile with ghost cadence by progress), `fix-run-cadence-empty` (complete; step samples exist but none usable), `fix-run-cadence-upload` (uploading; step samples including ones after the run end and inside a pause; finish not yet called), `fix-run-complete` (legacy, no step samples, metrics algorithm version 1), `fix-run-recovery` (existing Sprint02 run with a recovery phase), device `fix-device-1`. Shared oracle: `tests/fixtures/cadence_golden.json` (pytest and Kotlin read the same file).

## Scenarios

### Step samples are accepted and counted
- **Given:** `fix-run-cadence-upload` and `fix-device-1`
- **When:** a batch with `step` samples (event-time timestamps) is uploaded, then the same batch again
- **Then:** the first answer stores them and its cursors include a `step` entry; the second reports them as duplicates; nothing stored changes

### Step stream without timestamp is rejected
- **Given:** `fix-run-cadence-upload`
- **When:** a `step` sample without a valid UTC timestamp is uploaded
- **Then:** 422 `VALIDATION_ERROR` in the ApiError envelope and nothing is stored

### Finish verifies the step stream
- **Given:** `fix-run-cadence-upload` with all samples stored (location, heart rate, step)
- **When:** finish is called with matching expected counts including the step count, and once more with a wrong step count
- **Then:** the first result is `complete` and `verified_counts` contains the step count; the second is `incomplete` with a count mismatch naming stream `step`; the run stays `uploading` in that case

### Old finish body without a step count still works
- **Given:** an uploading run that has no step samples and `fix-device-1`
- **When:** finish is sent without `step` in the expected counts (old phone)
- **Then:** the result is `complete`; the step count in the answer is 0; an unrelated unknown key in the body still returns 422 `VALIDATION_ERROR`

### Finish stores cadence of the running phase only
- **Given:** `fix-run-cadence-upload` with steps during running, steps inside a pause, and steps after the run end
- **When:** finish completes with a run end
- **Then:** the stored cadence series covers only the running phase outside the pause; steps after the run end and inside the pause do not appear in it; all step samples remain stored and counted

### Step samples never count as heart rate
- **Given:** `fix-run-cadence` with step samples interleaved with heart-rate samples
- **When:** the run is recomputed
- **Then:** average and max heart rate, heart-rate series, split heart rates and recovery equal the values computed from heart-rate samples alone

### Run without steps has no cadence
- **Given:** `fix-run-complete` whose metrics carry the old algorithm version
- **When:** finish is replayed for it
- **Then:** its metrics are recomputed with the new algorithm version; distance, splits, average/max HR and series equal the previous values; its cadence stays empty (no object, no zero)

### Steady cadence is estimated
- **Given:** the golden vector with steps every 353 ms for two minutes
- **When:** cadence is computed
- **Then:** the series starts once enough steps are known, every point is about 170 steps per minute (within 0.1) with high confidence, points are 5 seconds apart, and the average equals the golden value

### A single missed step does not change the cadence
- **Given:** the golden vector with one isolated interval of about twice the normal interval between normal intervals
- **When:** cadence is computed
- **Then:** cadence stays at the normal value (no halving) and the confidence in the affected window is lower than in the steady vector; no step appears in the stored raw samples

### Two missed steps in a row are not corrected
- **Given:** the golden vector with an interval of about three times the normal interval
- **When:** cadence is computed
- **Then:** that interval is not turned into extra steps; the cadence does not jump to a tripled value; affected points are absent or keep the previous value according to the golden expectation

### A stop creates a gap, not a zero
- **Given:** the golden vector with steady running, a 5-second stop, then running again
- **When:** cadence is computed
- **Then:** points during the stop are absent (never 0); after restart there is a short warm-up without points before cadence reappears

### Running into walking does not invent steps
- **Given:** the golden vector with steady running followed by slower, evenly spaced walking steps
- **When:** cadence is computed
- **Then:** no interval is doubled or split; after the irregular phase the cadence re-anchors to the walking rhythm or stays absent per the golden expectation; no value is 0

### Irregular and sparse steps give no cadence
- **Given:** the golden vectors with stumbling intervals and with only three intervals in total
- **When:** cadence is computed
- **Then:** the series is empty and the average is empty; the stored cadence object exists with an empty series when steps existed

### Steps across a pause are not joined
- **Given:** the golden vector with a pause in the middle of steady running
- **When:** cadence is computed
- **Then:** no interval spans the pause, no point lies inside the pause, and cadence resumes after a short warm-up

### Duplicate and out-of-order step times are tolerated
- **Given:** the golden vector with duplicate timestamps and shuffled arrival order
- **When:** cadence is computed
- **Then:** the result equals the result for the sorted, de-duplicated steps

### Recalculation is deterministic
- **Given:** `fix-run-cadence`
- **When:** metrics are recomputed twice
- **Then:** the cadence object is identical both times and the raw step samples are unchanged

### Ghost cadence by progress is derived next to the profile
- **Given:** `fix-run-cadence` linked to a route and matched as a qualified ghost
- **When:** the ghost profile is requested through the native endpoint
- **Then:** the answer contains the usual profile points and `cadence_by_progress` as ascending 20 m buckets with cadence values, empty buckets absent, no value derived from speed

### Ghost without cadence reports null
- **Given:** a qualified ghost run without step samples (`fix-run-complete` linked to a route) and `fix-run-cadence-empty` linked to a route
- **When:** the ghost profile is requested
- **Then:** `cadence_by_progress` is null for both; the profile points are unchanged

### Ghost profile endpoint still requires auth and qualification
- **Given:** a non-qualified run and a request without token
- **When:** the ghost profile is requested
- **Then:** 404 for the non-qualified run and 401 without token, exactly as before

### Average cadence in the run row
- **Given:** `fix-run-cadence`, `fix-run-cadence-empty` and `fix-run-complete`
- **When:** the runs list and the run detail row are requested
- **Then:** `fix-run-cadence` has an average cadence value; the other two have none (null); no other column of any row changes

### Cadence series Dataset
- **Given:** `fix-run-cadence`
- **When:** `GET /api/runningtracker/runs/{id}/series?metric=cadence`
- **Then:** a Dataset (object type `run_series`, label Cadence) ordered by time ascending with the stored points, no confidence column, no gap filling

### Cadence series is empty or an error where appropriate
- **Given:** `fix-run-cadence-empty`, `fix-run-complete`, `fix-run-cadence-upload` (uploading), an unknown run id
- **When:** the cadence series is requested for each, and once with an unsupported metric
- **Then:** the first three return an empty Dataset (total 0); the unknown id returns 404 `NOT_FOUND`; the unsupported metric returns 422; pace, heart-rate and recovery series behave as before

### Deleting a run removes its cadence data
- **Given:** `fix-run-cadence`
- **When:** the run is deleted
- **Then:** its metrics (including cadence), step samples and route progress are gone and the cadence series endpoint returns 404

### Schema change is idempotent
- **Given:** a database that already has the Sprint02 schema, and an empty database
- **When:** the runtime schema is applied twice to each
- **Then:** both end with the same constraints and columns, existing samples survive, and a `step` sample can be stored while an unknown stream name is still rejected

### [Phone JVM] Phone and server agree on cadence
- **Given:** `tests/fixtures/cadence_golden.json`
- **When:** the Kotlin cadence estimator runs every vector
- **Then:** series points equal the golden expectations (spm within 0.1, confidence within 0.02, same absent points) — the same file the server tests use

### [Phone JVM] Step event time survives batching
- **Given:** a step event delivered 800 ms after it happened
- **When:** it is converted to a step sample
- **Then:** its timestamp is the event time (800 ms earlier than arrival), the monotonic stamp is kept, and the payload carries type, capture id, sequence and ISO UTC timestamp

### [Phone JVM] Capture store counts steps separately
- **Given:** a capture store upgraded from the previous schema version containing an old capture, and a fresh store
- **When:** location, heart-rate and step samples are appended
- **Then:** the old capture and its samples are intact after the upgrade; each stream increments only its own counter; the sequence is one strictly increasing counter shared by all streams; steps are never counted as heart rate

### [Phone JVM] Steps are never decoded as heart rate or location
- **Given:** a capture containing all three sample kinds
- **When:** the run controller loads the stored samples for a summary or recap
- **Then:** location and heart-rate lists contain only their own samples; step samples are ignored there

### [Phone JVM] Upload maps and counts the step stream
- **Given:** a pending-upload run with and without step samples
- **When:** samples are uploaded and the finish body is built
- **Then:** step samples are sent with stream name `step`; the finish body contains the step count only when it is greater than 0 (omitted, not 0 or null); the rest of the body is unchanged

### [Phone JVM] Activity recognition permission is only asked where needed
- **Given:** the permission logic
- **When:** the activity recognition capability is queried for Android 28, 29 and 34
- **Then:** Android 28 needs no permission (counts as granted); 29 and 34 require the activity recognition permission; location and Bluetooth results are unchanged

### [Phone JVM] Ghost profile decodes with and without cadence
- **Given:** a ghost profile JSON without `cadence_by_progress`, with null, and with a list
- **When:** decoded, cached and re-decoded
- **Then:** the first two give "no cadence recorded"; the list round-trips unchanged; the profile points are identical in all three

### [Phone JVM] Ghost cadence lookup by route position
- **Given:** a cadence-by-progress list with a gap in the middle
- **When:** the ghost cadence is asked at a covered position, between two buckets, inside the gap, before the first bucket by more than one bucket, and with unknown progress
- **Then:** covered positions give the (interpolated) bucket value; the gap, far-outside positions and unknown progress give none; nothing is derived from speed

### [Phone JVM] Metronome targets per mode
- **Given:** a ghost cadence of 170 and a manual cadence of 160
- **When:** the raw target is computed for Off, Match Ghost, Attack +2% and Manual, and for a ghost cadence of 90 and of 260
- **Then:** Off gives none; Match Ghost gives 170; Attack +2% gives 173.4; Manual gives 160; values outside the allowed range (90, 260 and their 1.02 multiples) give none; with no ghost cadence Match Ghost and Attack give none and Manual still gives 160

### [Phone JVM] Metronome target changes smoothly
- **Given:** the target smoother and a ghost cadence that jumps from 170 to 180 at once
- **When:** it is updated once per second for 15 seconds, then the raw target disappears for 10 seconds, then for 20 seconds, then returns
- **Then:** the output never changes by more than the slew limit per second; it reaches 180 after about 10 seconds; during the 10-second absence the last value is held; after 15 seconds of absence it is none; when the raw target returns it restarts from the new raw value

### [Phone JVM] Mode cycle and availability
- **Given:** runs with and without a ghost session
- **When:** the mode is cycled repeatedly, including from a restored mode that is not available
- **Then:** with a ghost the cycle is Off, Match Ghost, Attack +2%, Manual, Off; without a ghost it is Off, Manual, Off; an unavailable restored mode goes to Off

### [Phone JVM] Metronome controller drives the engine and persists settings
- **Given:** a metronome controller with a fake click engine and an in-memory settings store
- **When:** a run begins in a persisted mode, ticks run, the mode is cycled, the run pauses, resumes, and stops
- **Then:** the engine starts only for a mode other than Off; the target is handed over each tick (none while paused); cycling persists the mode and updates the notification label; stop silences the engine and clears the label; mode, manual cadence (clamped to the allowed range) and volume (clamped 0 to 1) survive a new controller

### [Phone JVM] Click timing is sample-accurate
- **Given:** the beat scheduler at 44.1 kHz
- **When:** one minute of audio is rendered at 150, 170 and 180 steps per minute, with 441-frame and 4410-frame buffers
- **Then:** the beat count equals the target exactly (±1) and beat positions deviate from the ideal grid by less than one frame in total (no drift); both buffer sizes produce identical audio; a target change affects only the interval after the next beat; target none renders silence and the first beat after silence starts immediately; the click peak stays at or below the configured quiet peak

### [Phone JVM] Audio timing does not depend on display updates
- **Given:** the metronome controller and the click engine's target hand-off
- **When:** ticks stop for 30 seconds (simulated stalled display refresh) while audio frames keep being rendered
- **Then:** the rendered beats keep the last target's timing without gaps or jumps

### [Phone JVM] Race chart derivations
- **Given:** a ghost profile and a run history with known progress and gap values
- **When:** the gap history, the 20-second race pace and the ghost section pace are derived, including a section shorter than 15 m and a position the ghost cannot answer
- **Then:** the gap history keeps about two minutes ordered by time (negative = ahead); the race pace uses the last 20 seconds and is none without enough movement; the ghost section pace equals the ghost's time over the same route section; short sections and unanswerable positions give none; the existing two-minute rolling pace and trend arrow results are unchanged

### [Phone JVM] Run settings defaults
- **Given:** an empty settings store, then stored garbage values
- **When:** the metronome mode, manual cadence and click volume are read
- **Then:** defaults are Off, 170 and the configured quiet volume; garbage values fall back to the defaults; out-of-range values are clamped; the heart-rate smoothing setting is unaffected

### [UI] Web run detail shows cadence
- **Given:** the run detail page with stubbed responses: a run row with average cadence 171, a cadence series, and the other existing responses
- **When:** the page is opened
- **Then:** the summary shows the average cadence as whole steps per minute, a Cadence chart card is shown, and the existing pace and heart-rate charts, recovery card, splits and comment are still shown

### [UI] Web run detail without cadence
- **Given:** stubbed responses where the run row has no average cadence and the cadence series is empty (legacy run)
- **When:** the page is opened
- **Then:** the average cadence shows a dash (never 0), the Cadence card shows "No cadence recorded.", no error is shown and all other cards render as before

### [UI — manual] Real cadence is recorded
- **Given:** a paired phone with the activity recognition permission granted, a real outdoor run of at least 10 minutes with a ghost race, H10 optional
- **When:** the run is finished and synced
- **Then:** the run appears in Atlas with an average cadence and a cadence chart that follow the phone's own sense of the run (compare with a known pace/cadence or another device); the raw step samples are visible in the run's sample counts

### [UI — manual] Permission denied still records the run
- **Given:** the activity recognition permission is denied at the first prompt
- **When:** a run is started, recorded and finished
- **Then:** the run starts without delay, GPS and heart rate record normally, the home panel states that cadence is not recorded, no further prompt appears without an explicit tap, and the run in Atlas has no cadence (dash, "No cadence recorded.")

### [UI — manual] Metronome plays quietly through headphones
- **Given:** headphones connected and a ghost with recorded cadence
- **When:** Match Ghost is selected on the race screen and the run proceeds
- **Then:** a very quiet click is heard, it follows the ghost's cadence along the route without sudden jumps, and the displayed target matches what is heard (check against a stopwatch over 30 seconds)

### [UI — manual] Attack mode
- **Given:** the same ghost and headphones
- **When:** Attack +2% is selected
- **Then:** the target shown and the click are about 2% above the ghost cadence at the same position

### [UI — manual] Screen off and music
- **Given:** a music or podcast app playing and the metronome on
- **When:** the screen is locked and the TWA/app is in the background for several minutes
- **Then:** the click continues at the right tempo, the music keeps playing without pausing or ducking, GPS and heart-rate samples keep arriving without gaps, and the step samples keep arriving

### [UI — manual] One-tap toggle and notification action
- **Given:** a running ghost race with the metronome on
- **When:** the mode chip is tapped repeatedly, and the notification action is used with the screen off
- **Then:** the mode cycles Off, Match Ghost, Attack +2%, Manual (ghost modes absent in a free run), the state persists for the next run, and the notification label follows the current mode

### [UI — manual] Ghost without cadence
- **Given:** a race against an old ghost recorded before this sprint
- **When:** Match Ghost is selected
- **Then:** the chip states that no cadence is recorded for this ghost, nothing is clicking, "Use manual cadence" switches to the manual fixed cadence (default 170, adjustable), and no cadence is derived from speed

### [UI — manual] Metronome stops with the run
- **Given:** a ghost race with the metronome on and a connected H10
- **When:** Finish Run is tapped
- **Then:** the click stops immediately, the recovery screen appears as in the previous sprint, no steps are recorded afterwards, and the metronome is also silent after a plain Finish and after Discard

### [UI — manual] Race screen left/right layout
- **Given:** a ghost race in portrait orientation
- **When:** the run proceeds for at least 3 minutes
- **Then:** the map and layout are as before; the lower area shows on the left the current time gap, the gaining/losing arrow, a 1-2 minute gap history and the 20-second pace beside the ghost's pace on the same section, and on the right the heart rate with the ghost's heart rate by position; the gap is never drawn on the same axis as pace; unknown values show a dash

### [UI — manual] GPS and heart-rate continuity under load
- **Given:** a 20+ minute run with steps, metronome, race chart and (if available) H10 active
- **When:** the raw samples are inspected after sync
- **Then:** GPS and heart-rate sample rates and gaps are indistinguishable from a comparable run without steps and metronome, and the click timing stayed steady while the display was busy or the screen was off

### [UI — manual] Headphone route change
- **Given:** the metronome on with Bluetooth headphones
- **When:** the headphones are disconnected and reconnected during the run
- **Then:** the observed behavior (click moves to the speaker or stops, and whether it resumes) is recorded in the test report as a known limitation (no speaker guard in this sprint)
