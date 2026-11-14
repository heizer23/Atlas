# Test Report — RunningTracker — Sprint02_RunFinishAndRecovery

**Verdict:** TESTS_PASSING
**Date:** 2026-11-13
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Finish with run end stores it and clips running statistics | test_native_sync.py::test_finish_with_run_end_stores_it_and_clips_running_statistics | backend | PASS | — |
| Finish without run end behaves as before | test_finish_without_run_end_behaves_as_before | backend | PASS | — |
| Run end before the start is rejected | test_run_end_before_the_start_is_rejected | backend | PASS | — |
| Run end after the training end is rejected | test_run_end_after_the_training_end_is_rejected | backend | PASS | — |
| Repeated finish keeps the stored run end | test_repeated_finish_of_a_complete_run_keeps_the_stored_run_end | backend | PASS | — |
| Replay recomputes a legacy run | test_replay_recomputes_a_legacy_run_without_inventing_recovery | backend | PASS | — |
| Old phone body accepted, unknown keys not | test_old_phone_body_is_accepted_and_unknown_keys_are_not | backend | PASS | — |
| HRR values from the end of running | test_web_api.py::test_recomputing_a_recovery_run_gives_the_golden_hrr_values; test_recovery.py::test_recovery_values_follow_hrr1_golden_vectors | backend | PASS | — |
| Recovery values empty, not zero | test_recovery_values_follow_hrr1_golden_vectors (golden vectors) | backend | PASS | — |
| Artifacts ignored, raw samples stay | test_validity_never_alters_values_and_removes_only_artifacts | backend | PASS | — |
| Recovery curve without zero-filling | test_recovery_series_covers_the_recovery_phase_without_zero_filling | backend | PASS | — |
| Run without heart rate has empty recovery | test_run_without_heart_rate_has_a_null_recovery_row_and_an_empty_series | backend | PASS | — |
| Recovery Dataset for a run with recovery | test_recovery_dataset_for_a_run_with_recovery | backend | PASS | — |
| Recovery Dataset empty for legacy/uploading, 404 unknown | test_recovery_dataset_is_empty_for_legacy_and_uploading_runs_and_404_for_unknown | backend | PASS | — |
| Series metric validation | test_series_metric_validation | backend | PASS | — |
| History averages exclude recovery | test_history_averages_exclude_recovery | backend | PASS | — |
| Deleting a run removes recovery data | test_deleting_a_recovery_run_removes_its_recovery_data | backend | PASS | — |
| [Phone JVM] Lifecycle supports recovery phase | RunLifecycleTest.allEventsAppliedToAllStates / recoveryPathWalksTheWholeLifecycle... | Phone JVM | PASS | — |
| [Phone JVM] No H10 skips recovery | RunLifecycleTest.recoveryGateOffersRecoveryOnlyWithALiveHeartRate | Phone JVM | PASS | — |
| [Phone JVM] Smoothing never turns missing into zero | HrSmoothingTest (5 tests) | Phone JVM | PASS | — |
| [Phone JVM] Phone and server agree on recovery values | RecoveryMetricsTest.phoneAndServerAgreeOnTheGoldenVectors | Phone JVM | PASS | — |
| [Phone JVM] Summary excludes recovery segment | RecapBuilderTest.summaryAtRunEndExcludesTheRecoverySegment (+2) | Phone JVM | PASS | — |
| [Phone JVM] Final standing and achievements | FinishStandingTest (7 tests) | Phone JVM | PASS | — |
| [Phone JVM] Old run metadata still decodes | RunMetaCompatTest (3 tests) | Phone JVM | PASS | — |
| [Phone JVM] Finish request carries run end only when set | AtlasClientTest.finishBodyCarriesTheRunEndOnlyWhenSet | Phone JVM | PASS | — |
| [Phone JVM] Recovery tracker and reminder | RecoveryMetricsTest.trackerFillsHrr60AndHrr120OnlyOnceTheirWindowsAreComplete (+ trackerWithoutReadings...) | Phone JVM | PASS | — |
| [UI] Web run detail shows Recovery card | running_web.spec.ts: run detail shows the Recovery card | UI | PASS | — |
| [UI] Web run detail hides Recovery card without recovery | running_web.spec.ts: run detail hides the Recovery card without recovery... | UI | PASS | — |
| [UI — manual] Finish Run starts the recovery screen | — | manual | MANUAL (untested) | requires phone/H10 |
| [UI — manual] Finish Training shows the recap | — | manual | MANUAL (untested) | requires phone |
| [UI — manual] Run without H10 finishes directly | — | manual | MANUAL (untested) | requires phone |
| [UI — manual] Kill during recovery | — | manual | MANUAL (untested) | requires phone |
| [UI — manual] H10 disconnect during recovery | — | manual | MANUAL (untested) | requires phone/H10 |
| [UI — manual] GPS stops and HR continues at the run end | — | manual | MANUAL (untested) | requires real run |
| [UI — manual] Smoothing setting | — | manual | MANUAL (untested) | requires phone |

## Test output

```
Backend (atlas-runningtracker-test): 102 passed, 3 warnings (deprecation only) in 11.46s
Playwright (running_web.spec.ts): 9 passed (11.0s)
Phone JVM (:app:testDebugUnitTest --offline): BUILD SUCCESSFUL; task reported UP-TO-DATE (cached prior run);
  result XMLs in app/build/test-results/testDebugUnitTest: 115 tests, 0 failures, 0 errors, 0 skipped
```

## Failure Analysis

All automated scenarios passed. Note: the Gradle test task was UP-TO-DATE, so the JVM result reflects the last execution against unchanged inputs, not a fresh run.

Untested (MANUAL, not passing, need human verification): Finish Run starts the recovery screen; Finish Training shows the recap; Run without H10 finishes directly; Kill during recovery; H10 disconnect during recovery; GPS stops and heart rate continues at the run end; Smoothing setting.

## Required Action

Proceed to the next stage; a human must verify the seven manual scenarios on a physical phone.
