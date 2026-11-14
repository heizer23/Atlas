# Test Report — RunningTracker — Sprint03_CadenceAndLiveRacing

**Verdict:** TESTS_PASSING
**Date:** 2026-11-14
**Fix iteration:** 1

## Results

Backend: pytest in `atlas-runningtracker-test`, 141 passed / 0 failed (rebuilt via `03_Application/RunningTracker/compose.yml`, service `runningtracker-test`; the service is not in `01_System/test/compose.test.yml`).
Web UI: Playwright, 11 passed (includes the two new cadence tests). Phone JVM: `:app:testDebugUnitTest --offline --rerun-tasks`, BUILD SUCCESSFUL, 0 failures across 28 suites (143 tests).

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Step samples accepted and counted | test_native_sync::test_step_samples_are_accepted_and_counted_idempotently | backend | PASS | — |
| Step stream without timestamp rejected | test_step_sample_without_valid_timestamp_is_rejected | backend | PASS | — |
| Finish verifies the step stream | test_finish_verifies_the_step_stream | backend | PASS | — |
| Old finish body without step count | test_old_finish_body_without_step_count_still_works (+ test_old_phone_body_is_accepted_and_unknown_keys_are_not) | backend | PASS | — |
| Finish stores cadence of running phase only | test_finish_stores_cadence_of_the_running_phase_only, test_compute_metrics_clips_steps_to_running_phase_and_pauses | backend | PASS | — |
| Step samples never count as heart rate | test_step_rows_never_count_as_heart_rate_and_cadence_is_deterministic | backend | PASS | — |
| Run without steps has no cadence | test_run_without_steps_has_null_cadence_and_unchanged_values, test_replay_recomputes_a_legacy_run_without_inventing_recovery | backend | PASS | — |
| Steady cadence / single missed step / two missed / stop gap / run-to-walk / irregular-sparse / across pause / duplicates and order | tests/test_cadence.py (golden vectors, 23 tests incl. these cases) | backend | PASS | — |
| Recalculation is deterministic | test_step_rows_never_count_as_heart_rate_and_cadence_is_deterministic | backend | PASS | — |
| Ghost cadence by progress derived | test_ghost_profile_carries_cadence_by_progress, test_cadence_by_progress_* | backend | PASS | — |
| Ghost without cadence reports null | test_ghost_profile_cadence_is_null_without_usable_steps | backend | PASS | — |
| Ghost endpoint still requires auth/qualification | test_ghost_profile_auth_and_qualification_unchanged | backend | PASS | — |
| Average cadence in run row | test_average_cadence_in_run_row | backend | PASS | — |
| Cadence series Dataset | test_cadence_series_dataset | backend | PASS | — |
| Cadence series empty / error cases | test_cadence_series_empty_and_error_cases | backend | PASS | — |
| Deleting a run removes cadence data | test_deleting_a_cadence_run_removes_its_cadence_data | backend | PASS | — |
| Schema change idempotent | test_schema_with_step_stream_is_idempotent_and_still_rejects_unknown_streams | backend | PASS | — |
| [Phone JVM] Phone and server agree on cadence | CadenceEstimatorTest.everyGoldenVectorMatchesTheServer (+ gapsAreAbsentNeverZero, atIsDeterministicAndNullWithoutSteps) | JVM | PASS | — |
| [Phone JVM] Step event time survives batching | StepCaptureTest.batchedStepKeepsItsEventTime | JVM | PASS | — |
| [Phone JVM] Capture store counts steps separately | StepCaptureTest.storeCountsStepsSeparatelyAndSharesOneSequence, versionTwoDatabaseUpgradesKeepingCapturesAndSamples, CaptureStoreV2Test | JVM | PASS | — |
| [Phone JVM] Steps never decoded as heart rate or location | StepsNotDecodedTest.stepsAreNeverDecodedAsHeartRateOrLocation (XML: tests=1, failures=0, errors=0) | JVM | PASS | — |
| [Phone JVM] Upload maps and counts the step stream | AtlasClientTest.streamNamesAreMappedAndPayloadIsUnchanged, stepStreamIsSentAndCountedOnlyWhenPresent | JVM | PASS | — |
| [Phone JVM] Activity recognition permission | PermissionLogicTest / StepCaptureTest.activityRecognitionPermissionOnlyFromAndroid10 | JVM | PASS | — |
| [Phone JVM] Ghost profile decodes with/without cadence | GhostClientTest.ghostProfileDecodesWithAndWithoutCadenceAndRoundTrips | JVM | PASS | — |
| [Phone JVM] Ghost cadence lookup by route position | MetronomeTargetTest.ghostCadenceLookupInterpolatesAndHonoursGaps | JVM | PASS | — |
| [Phone JVM] Metronome targets per mode | MetronomeTargetTest.rawTargetPerMode | JVM | PASS | — |
| [Phone JVM] Metronome target changes smoothly | MetronomeTargetTest.smootherNeverJumpsHoldsThenSilencesAndRestarts | JVM | PASS | — |
| [Phone JVM] Mode cycle and availability | MetronomeTargetTest.modeCycleAndAvailability | JVM | PASS | — |
| [Phone JVM] Metronome controller drives engine, persists settings | MetronomeTargetTest.controllerDrivesTheEngineAndPersistsSettings | JVM | PASS | — |
| [Phone JVM] Click timing sample-accurate | BeatSchedulerTest (5 tests) | JVM | PASS | — |
| [Phone JVM] Audio timing independent of display | MetronomeTargetTest.audioKeepsItsTimingWhenTheDisplayTickStalls | JVM | PASS | — |
| [Phone JVM] Race chart derivations | RaceChartTest (4 tests) + LiveInsightsTest (existing, passing) | JVM | PASS | — |
| [Phone JVM] Run settings defaults | RunMetaCompatTest.metronomeSettingsDefaultsGarbageAndClamping, smoothingSettingDefaultsToFiveSecondsWhenUnsetOrUnknown | JVM | PASS | — |
| [UI] Web run detail shows cadence | running_web.spec.ts: run detail shows cadence stat and card | UI | PASS | — |
| [UI] Web run detail without cadence | running_web.spec.ts: run detail without cadence shows a dash and the neutral note | UI | PASS | — |
| [UI — manual] Real cadence is recorded | — | manual | MANUAL (untested) | Needs a physical phone and an outdoor run |
| [UI — manual] Permission denied still records the run | — | manual | MANUAL (untested) | Device |
| [UI — manual] Metronome plays quietly through headphones | — | manual | MANUAL (untested) | Device and audio |
| [UI — manual] Attack mode | — | manual | MANUAL (untested) | Device and audio |
| [UI — manual] Screen off and music | — | manual | MANUAL (untested) | Device |
| [UI — manual] One-tap toggle and notification action | — | manual | MANUAL (untested) | Device |
| [UI — manual] Ghost without cadence | — | manual | MANUAL (untested) | Device |
| [UI — manual] Metronome stops with the run | — | manual | MANUAL (untested) | Device and H10 |
| [UI — manual] Race screen left/right layout | — | manual | MANUAL (untested) | Device |
| [UI — manual] GPS and heart-rate continuity under load | — | manual | MANUAL (untested) | Device |
| [UI — manual] Headphone route change | — | manual | MANUAL (untested) | Device; the observed behavior must be recorded as a known limitation |

## Test output

```
Backend: ======================= 141 passed, 3 warnings in 20.33s =======================
         (warnings: FastAPI on_event / starlette httpx deprecations only)
Playwright: 11 passed (13.4s)
Gradle: BUILD SUCCESSFUL (--rerun-tasks); 28 suites, 143 tests, 0 failures, 0 errors, 0 skipped
```

## Failure Analysis

All scenarios passed. StepsNotDecodedTest executed in this run (confirmed in TEST-net.linspad.atlasphone.running.StepsNotDecodedTest.xml, 1 test, 0 failures).

MANUAL scenarios (untested, not failing, need a human on a physical device): Real cadence is recorded; Permission denied still records the run; Metronome plays quietly through headphones; Attack mode; Screen off and music; One-tap toggle and notification action; Ghost without cadence; Metronome stops with the run; Race screen left/right layout; GPS and heart-rate continuity under load; Headphone route change.

## Required Action

Proceed past the test stage; a human must verify the 11 `[UI — manual]` scenarios on a device.
