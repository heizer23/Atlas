# Test Report — HabitTracker — Sprint01_Core

**Verdict:** TESTS_PASSING
**Date:** 2026-10-01
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Habit list — starter seed present on first run | test_habit_list_starter_seed_on_first_run | backend | PASS | — |
| Habit list — seeding is a one-time, table-emptiness check | test_habit_list_seeding_is_one_time_table_emptiness_check | backend | PASS | — |
| Create habit — success | test_create_habit_success | backend | PASS | — |
| Create habit — missing name is rejected | test_create_habit_missing_name_rejected | backend | PASS | — |
| Update habit — partial update leaves other fields unchanged | test_update_habit_partial_update_leaves_other_fields_unchanged | backend | PASS | — |
| Update habit — explicit null clears description | test_update_habit_explicit_null_clears_description | backend | PASS | — |
| Update habit — omitting description leaves it unchanged | test_update_habit_omitting_description_leaves_it_unchanged | backend | PASS | — |
| Update habit — explicit null on name is rejected | test_update_habit_explicit_null_on_name_is_rejected | backend | PASS | — |
| Update habit — archiving via end_date | test_update_habit_archiving_via_end_date | backend | PASS | — |
| Update habit — un-archiving by explicit null | test_update_habit_unarchiving_by_explicit_null | backend | PASS | — |
| Update habit — end_date before active_from is rejected | test_update_habit_end_date_before_active_from_is_rejected | backend | PASS | — |
| Update habit — unknown id | test_update_habit_unknown_id | backend | PASS | — |
| Reorder habits — full permutation including a swap | test_reorder_habits_full_permutation_including_a_swap | backend | PASS | — |
| Reorder habits — mismatched id set is rejected | test_reorder_habits_mismatched_id_set_is_rejected | backend | PASS | — |
| Daily review — unreviewed day uses current defaults | test_unreviewed_day_uses_current_defaults | backend | PASS | — |
| Daily review — draft save preserves edited values and merges new habits | test_draft_preserves_edited_values_and_merges_newly_active_habit | backend | PASS | — |
| Daily review — editing a habit's default does not change an existing draft | test_draft_preserves_edited_values_and_merges_newly_active_habit (combined, same function, 2nd half) | backend | PASS | — |
| Daily review — confirming a day stamps confirmed_at and counts it | test_confirm_freezes_display_and_is_idempotent (combined, 1st phase) | backend | PASS | — |
| Daily review — confirmed day display is frozen against later habit edits | test_confirm_freezes_display_and_is_idempotent (combined, 2nd phase) | backend | PASS | — |
| Daily review — PUT is idempotent | test_confirm_freezes_display_and_is_idempotent (combined, 3rd phase) | backend | PASS | — |
| Daily review — PUT rejects a habit_results set that omits an expected habit | test_put_rejects_mismatched_habit_sets (combined, 1st phase) | backend | PASS | — |
| Daily review — PUT rejects a habit_results set that adds an unexpected habit | test_put_rejects_mismatched_habit_sets (combined, 2nd phase) | backend | PASS | — |
| Daily review — re-confirming accepts exactly the previously saved set even after the active window changes | test_reconfirm_accepts_frozen_set_after_active_window_changes | backend | PASS | — |
| Daily review — editing an already-confirmed day downgrades it to draft | test_editing_confirmed_day_downgrades_to_draft | backend | PASS | — |
| Daily review — malformed date is rejected | test_malformed_date_is_rejected | backend | PASS | — |
| Reports — grid cell states cover all four cases | test_grid_cell_states_cover_all_four_cases | backend | PASS | — |
| Reports — per-habit rate omits percentage when eligible is zero | test_per_habit_rate_omits_percentage_when_eligible_is_zero | backend | PASS | — |
| Reports — period-level elapsed days never counts future dates | test_elapsed_days_never_counts_future_dates | backend | PASS | — |
| Reports — empty habit set still returns a valid period_summary | test_empty_habit_set_still_returns_valid_period_summary | backend | PASS | — |
| Reports — invalid period parameter is rejected | test_invalid_period_parameter_is_rejected | backend | PASS | — |
| [UI — manual] Daily Review shows a clear Unreviewed/Draft/Confirmed status | — | manual | MANUAL | requires human verification |
| [UI — manual] Checkbox edits are never lost on navigation away | — | manual | MANUAL | requires human verification |
| [UI — manual] Reports grid cell drill-through opens the correct day | — | manual | MANUAL | requires human verification |

Two additional non-spec smoke tests also pass: `test_habittracker_proxy_returns_json` and
`test_shell_serves_app_at_basepath` (`tests/test_shell_proxy.py`), verifying nginx proxy
routing and shell registration end-to-end against the live `atlas-shell` container.

No `tests/ui/` directory exists in the component, which is correct — all three `[UI]`
scenarios in `10_test_spec.md` are labeled `[UI — manual]`, so no `.spec.ts` automation
is expected this sprint; Playwright was not run.

## Test output

```
============================= test session starts ==============================
platform linux -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0 -- /usr/local/bin/python3.12
cachedir: .pytest_cache
rootdir: /app
configfile: pyproject.toml
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 28 items

tests/test_habits.py::test_habit_list_starter_seed_on_first_run PASSED   [  3%]
tests/test_habits.py::test_habit_list_seeding_is_one_time_table_emptiness_check PASSED [  7%]
tests/test_habits.py::test_create_habit_success PASSED                   [ 10%]
tests/test_habits.py::test_create_habit_missing_name_rejected PASSED     [ 14%]
tests/test_habits.py::test_update_habit_partial_update_leaves_other_fields_unchanged PASSED [ 17%]
tests/test_habits.py::test_update_habit_explicit_null_clears_description PASSED [ 21%]
tests/test_habits.py::test_update_habit_omitting_description_leaves_it_unchanged PASSED [ 25%]
tests/test_habits.py::test_update_habit_explicit_null_on_name_is_rejected PASSED [ 28%]
tests/test_habits.py::test_update_habit_archiving_via_end_date PASSED    [ 32%]
tests/test_habits.py::test_update_habit_unarchiving_by_explicit_null PASSED [ 35%]
tests/test_habits.py::test_update_habit_end_date_before_active_from_is_rejected PASSED [ 39%]
tests/test_habits.py::test_update_habit_unknown_id PASSED                [ 42%]
tests/test_habits.py::test_reorder_habits_full_permutation_including_a_swap PASSED [ 46%]
tests/test_habits.py::test_reorder_habits_mismatched_id_set_is_rejected PASSED [ 50%]
tests/test_reports.py::test_grid_cell_states_cover_all_four_cases PASSED [ 53%]
tests/test_reports.py::test_per_habit_rate_omits_percentage_when_eligible_is_zero PASSED [ 57%]
tests/test_reports.py::test_elapsed_days_never_counts_future_dates PASSED [ 60%]
tests/test_reports.py::test_empty_habit_set_still_returns_valid_period_summary PASSED [ 64%]
tests/test_reports.py::test_invalid_period_parameter_is_rejected PASSED  [ 67%]
tests/test_reviews.py::test_unreviewed_day_uses_current_defaults PASSED  [ 71%]
tests/test_reviews.py::test_draft_preserves_edited_values_and_merges_newly_active_habit PASSED [ 75%]
tests/test_reviews.py::test_confirm_freezes_display_and_is_idempotent PASSED [ 78%]
tests/test_reviews.py::test_put_rejects_mismatched_habit_sets PASSED     [ 82%]
tests/test_reviews.py::test_reconfirm_accepts_frozen_set_after_active_window_changes PASSED [ 85%]
tests/test_reviews.py::test_editing_confirmed_day_downgrades_to_draft PASSED [ 89%]
tests/test_reviews.py::test_malformed_date_is_rejected PASSED            [ 92%]
tests/test_shell_proxy.py::test_habittracker_proxy_returns_json PASSED   [ 96%]
tests/test_shell_proxy.py::test_shell_serves_app_at_basepath PASSED      [100%]

=============================== warnings summary ===============================
tests/test_habits.py::test_habit_list_starter_seed_on_first_run
  /app/backend/main.py:34: DeprecationWarning:
          on_event is deprecated, use lifespan event handlers instead.
    @app.on_event("startup")
tests/test_habits.py::test_habit_list_starter_seed_on_first_run
  /app/tests/conftest.py:106: StarletteDeprecationWarning: Using `httpx` with
  `starlette.testclient` is deprecated; install `httpx2` instead.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 28 passed, 3 warnings in 2.72s ========================
```

Suite re-run a second time (same container, same command) to confirm determinism and
that the one test using a locally isolated truncate (`test_habit_list_starter_seed_on_first_run`,
logged as `EVD-2026-10-01-007`/`EVD-2026-10-01-001`) does not corrupt state for
subsequent tests — confirmed: the autouse `clean_tables` fixture in `conftest.py`
re-truncates and reloads `fixtures.sql` before every test regardless of what the prior
test did, so the local truncate is fully contained to its own test. Second run: identical
result, `28 passed`.

## Failure Analysis

All scenarios passed. All 30 non-UI scenarios in `10_test_spec.md` map to a concrete,
passing pytest function (14 in `test_habits.py` 1:1, 11 in `test_reviews.py` combined
into 7 functions where the spec's own scenario text explicitly builds sequentially on
a shared prior state — e.g. "the draft from the previous scenario", "confirmed in the
previous scenario" — and 5 in `test_reports.py` 1:1). No scenario is silently untested.

The three `[UI — manual]` scenarios (status indicator transitions, checkbox-edit
survival on navigation, grid cell drill-through) have no `.spec.ts` files, which is
correct per `10_test_spec.md`'s own labeling — they require human verification and are
recorded here as `MANUAL`, not `PASS`.

Independently verified (not taken on the implementer's self-report): rebuilt and
restarted the `-test` container fresh, ran the full suite twice back-to-back (28/28
both times), and confirmed in source that the reported psycopg2 fix
(`habit_id = any(%s::uuid[])` in `backend/routers/reports.py:140`) is present and is
exercised by `test_grid_cell_states_cover_all_four_cases`.

Process note (not a test failure, not blocking `TESTS_PASSING`): the central test stack
file `01_System/test/compose.test.yml` has no `habittracker-test` service entry — only
the component-local `03_Application/HabitTracker/compose.yml` defines it. The already-
running `atlas-habittracker-test` container was evidently built/started via the local
compose file directly rather than the central one. This test run rebuilt via the local
`03_Application/HabitTracker/compose.yml` file instead, which has the correct service
definition and produced a correctly running, correctly configured (`ATLAS_PG_DB=atlas_test`)
container. This is worth closing before this component is considered fully onboarded
to the shared test-stack convention, but does not affect the validity of this test run.

## Required Action

None — proceed to `/sprint-close`. (Optional housekeeping, non-blocking: add a
`habittracker-test` service entry to `01_System/test/compose.test.yml` mirroring the
other `03_Application` entries, so future test runs don't need to fall back to the
component-local compose file.)
