# Test Report — RunningTracker — Sprint04_GhostCoach

**Verdict:** TESTS_PASSING
**Date:** 2026-11-15
**Fix iteration:** 0

## Results

Backend (pytest, atlas-runningtracker-test): 213 passed, 0 failed. UI (Playwright): 20 passed, 0 failed.

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| AI is off by default | test_coach_api::test_ai_is_off_by_default | backend | PASS | — |
| Enabling AI requires current consent version | test_enabling_ai_requires_the_current_consent_version | backend | PASS | — |
| Disabling AI clears consent | test_disabling_ai_clears_consent | backend | PASS | — |
| Goal text null versus omitted | test_goal_text_null_versus_omitted | backend | PASS | — |
| Preview shows exactly what would be sent | test_preview_is_byte_identical_to_what_is_sent_and_stored | backend | PASS | — |
| Payload contains only allow-listed fields | test_coach_payload::test_payload_from_fixtures_contains_only_allow_listed_fields_and_no_identifying_values (+ missing_values_are_null_never_zero) | backend | PASS | — |
| Payload history is bounded | test_history_is_newest_first_and_oldest_dropped_when_the_document_is_too_large | backend | PASS | — |
| Key never leaves the server side | test_key_never_appears_in_responses_logs_or_rows (+ request_to_provider_carries_the_key_only_in_the_header) | backend | PASS | — |
| Host outside allow-list refused | test_host_outside_the_allow_list_is_refused_without_a_call | backend | PASS | — |
| Analysis happy path | test_analysis_happy_path | backend | PASS | — |
| Analysis idempotent unless forced | test_analysis_is_idempotent_unless_forced | backend | PASS | — |
| Analysis check order | test_analysis_check_order | backend | PASS | — |
| Provider failure leaves no analysis | test_provider_failure_leaves_no_analysis_and_a_retry_succeeds | backend | PASS | — |
| Invalid provider output rejected | test_invalid_provider_output_is_rejected | backend | PASS | — |
| Invalid plan keeps the assessment | test_invalid_plan_keeps_the_assessment | backend | PASS | — |
| Interval plans stay occasional | test_interval_plans_stay_occasional (+ test_coach_plan interval_frequency) | backend | PASS | — |
| Inferred profile needs enough runs | test_inferred_profile_needs_enough_runs, test_inferred_profile_with_ten_runs_is_capped_and_filtered | backend | PASS | — |
| Analysis read for run detail | test_analysis_read_for_the_run_detail | backend | PASS | — |
| Measured profile deterministic, never zero-filled | test_coach_profile (4 tests) | backend | PASS | — |
| Profile read order | test_profile_read_order | backend | PASS | — |
| Next session selection | test_next_session_selection | backend | PASS | — |
| Accept a plan unchanged | test_accept_a_plan_unchanged | backend | PASS | — |
| Modify with null versus omitted | test_modify_with_null_versus_omitted | backend | PASS | — |
| Invalid overrides rejected | test_invalid_overrides_are_rejected, test_clearing_hr_on_an_hr_controlled_plan_is_rejected | backend | PASS | — |
| Forbidden transitions | test_forbidden_transitions | backend | PASS | — |
| Plan history list | test_plan_history_list | backend | PASS | — |
| Phone fetches the active plan | test_phone_fetches_the_active_plan | backend | PASS | — |
| Finish links plan and stores outcome | test_finish_links_the_plan_and_stores_the_outcome | backend | PASS | — |
| Finish ignores unknown/unusable plan ids | test_finish_ignores_unknown_or_unusable_plan_ids | backend | PASS | — |
| Coach hook errors never break finish | test_coach_hook_errors_never_break_finish | backend | PASS | — |
| Existing behavior unchanged without coaching | test_existing_behavior_unchanged_without_coaching | backend | PASS | — |
| Plan schema golden cases (server side) | test_coach_plan::test_golden_plan_cases[*], test_golden_override_cases[*] | backend | PASS | Phone-side parser half is covered only by the untested JVM CoachPlanTest |
| [Phone JVM] all 13 engine/session/plan scenarios | CoachEngineTest.kt, CoachSessionTest.kt, CoachPlanTest.kt (exist) | Phone JVM | NOT RUN | No JDK on the runner (JAVA_HOME unset, gradlew not executable); not routinely runnable. Reported untested, not failed |
| [UI] Run detail shows stored assessment | running_web.spec.ts:330 | UI | PASS | — |
| [UI] Analyse run with consent missing | running_web.spec.ts:341 | UI | PASS | — |
| [UI] Analyse run success | running_web.spec.ts:362 | UI | PASS | — |
| [UI] Consent flow on Coach page | running_web.spec.ts:410, :425 | UI | PASS | — |
| [UI] Accept, modify, disregard | running_web.spec.ts:432, :443, :456 | UI | PASS | — |
| [UI] Profile and history render | running_web.spec.ts:463 | UI | PASS | — |
| [UI — manual] Phone coach card and offline plan | — | manual | MANUAL | Untested, needs device |
| [UI — manual] Coaching a real session | — | manual | MANUAL | Untested, needs device |
| [UI — manual] First complete lifecycle | — | manual | MANUAL | Untested, needs real key and device |

## Test output

```
docker exec atlas-runningtracker-test pytest tests/ -v
======================= 213 passed, 3 warnings in 34.67s =======================
(3 deprecation warnings only: on_event, httpx/starlette)

docker exec atlas-playwright npx playwright test 03_Application/RunningTracker/tests/ui/ ...
  20 passed (16.6s)
```

## Failure Analysis

All runnable scenarios passed. Not covered:
- MANUAL (untested): Phone coach card and offline plan; Coaching a real session; First complete lifecycle.
- Phone JVM scenarios not run (no JDK available to the runner). Test files exist in 01_System/AtlasPhone/app/src/test/java/net/linspad/atlasphone/running/ (CoachEngineTest, CoachSessionTest, CoachPlanTest) but their results are unknown. The phone half of plan-schema parity is therefore unverified.
- Rebuild note: `compose.test.yml` has no runningtracker service ("no such service"), so the container was not rebuilt by this run. The existing atlas-runningtracker-test container (created minutes before the run) was used as is.

## Required Action

Proceed to close the sprint; run the Phone JVM tests (`./gradlew testDebugUnitTest`) on a JDK-equipped machine and perform the three manual device scenarios.
