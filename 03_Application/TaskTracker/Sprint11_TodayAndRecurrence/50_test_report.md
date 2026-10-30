# Test Report — TaskTracker — Sprint11_TodayAndRecurrence

**Verdict:** TESTS_PASSING
**Date:** 2026-10-30
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Agenda — overdue task bucketed | test_agenda_overdue_task_bucketed | backend | PASS | — |
| Agenda — due today bucketed | test_agenda_due_today_bucketed | backend | PASS | — |
| Agenda — upcoming window boundary | test_agenda_upcoming_window_boundary | backend | PASS | — |
| Agenda — scheduled status uses scheduled_at | test_agenda_scheduled_status_uses_scheduled_at | backend | PASS | — |
| Agenda — non-scheduled status uses due_date | test_agenda_non_scheduled_status_uses_due_date | backend | PASS | — |
| Agenda — done tasks excluded | test_agenda_done_tasks_excluded | backend | PASS | — |
| Agenda — training_unit tasks excluded | test_agenda_training_unit_tasks_excluded | backend | PASS | — |
| Agenda — undated tasks excluded | test_agenda_undated_tasks_excluded | backend | PASS | — |
| Agenda — ordering | test_agenda_ordering | backend | PASS | — |
| Agenda — empty result | test_agenda_empty_result | backend | PASS | — |
| Agenda — auto-promotion runs before the query and persists | test_agenda_auto_promotion_runs_before_query_and_persists | backend | PASS | — |
| Agenda — labels embedded and LabelEngine failure tolerated | test_agenda_labels_embedded_and_label_engine_failure_tolerated | backend | PASS | — |
| Agenda — existing views unchanged | test_agenda_existing_views_unchanged | backend | PASS | — |
| Recurrence — create with valid recurrence | test_recurrence_create_with_valid_recurrence | backend | PASS | — |
| Recurrence — label formats | test_recurrence_label_formats | backend | PASS | — |
| Recurrence — create validation errors | test_recurrence_create_validation_errors | backend | PASS | — |
| Recurrence — after_completion without dates allowed | test_recurrence_after_completion_without_dates_allowed | backend | PASS | — |
| Recurrence — PATCH null clears recurrence | test_recurrence_patch_null_clears_recurrence | backend | PASS | — |
| Recurrence — PATCH omit leaves recurrence unchanged | test_recurrence_patch_omit_leaves_recurrence_unchanged | backend | PASS | — |
| Recurrence — PATCH explicit null on interval or mode rejected | test_recurrence_patch_explicit_null_on_interval_or_mode_rejected | backend | PASS | — |
| Recurrence — PATCH clearing the only date of a fixed task rejected | test_recurrence_patch_clearing_the_only_date_of_a_fixed_task_rejected | backend | PASS | — |
| Recurrence — due_date explicit null clears on a normal task | test_recurrence_due_date_explicit_null_clears_on_a_normal_task | backend | PASS | — |
| Recurrence — daily fixed spawns next day | test_recurrence_daily_fixed_spawns_next_day | backend | PASS | — |
| Recurrence — weekly fixed with interval | test_recurrence_weekly_fixed_with_interval | backend | PASS | — |
| Recurrence — monthly fixed | test_recurrence_monthly_fixed | backend | PASS | — |
| Recurrence — month-end clamp (date arithmetic) | test_recurrence_month_end_clamp_date_arithmetic | backend | PASS | — |
| Recurrence — long-overdue catch-up (date arithmetic) | test_recurrence_long_overdue_catch_up_date_arithmetic | backend | PASS | — |
| Recurrence — long-overdue catch-up through the API | test_recurrence_long_overdue_catch_up_through_the_api | backend | PASS | — |
| Recurrence — fixed result equal to today is pushed forward | test_recurrence_fixed_result_equal_to_today_is_pushed_forward | backend | PASS | — |
| Recurrence — after_completion uses completion date | test_recurrence_after_completion_uses_completion_date | backend | PASS | — |
| Recurrence — after_completion with no dates | test_recurrence_after_completion_with_no_dates | backend | PASS | — |
| Recurrence — every freq and mode combination yields exactly one successor | test_recurrence_every_freq_and_mode_combination_yields_exactly_one_successor | backend | PASS | — |
| Recurrence — successor copies content and resets completion fields | test_recurrence_successor_copies_content_and_resets_completion_fields | backend | PASS | — |
| Recurrence — labels copied to successor | test_recurrence_labels_copied_to_successor | backend | PASS | — |
| Recurrence — label copy failure does not fail completion | test_recurrence_label_copy_failure_does_not_fail_completion | backend | PASS | — |
| Recurrence — undo and redo spawn no duplicate | test_recurrence_undo_and_redo_spawn_no_duplicate | backend | PASS | — |
| Recurrence — repeated done does not respawn | test_recurrence_repeated_done_does_not_respawn | backend | PASS | — |
| Recurrence — non-recurring completion spawns nothing | test_recurrence_non_recurring_completion_spawns_nothing | backend | PASS | — |
| Recurrence — clearing recurrence while completing spawns nothing | test_recurrence_clearing_recurrence_while_completing_spawns_nothing | backend | PASS | — |
| Recurrence — scheduled recurring task spawns scheduled successor with blocker | test_recurrence_scheduled_recurring_task_spawns_scheduled_successor_with_blocker | backend | PASS | — |
| Recurrence — scheduled task completed through the edit-form payload | test_recurrence_scheduled_task_completed_through_the_edit_form_payload | backend | PASS | — |
| Recurrence — calendar failure does not fail completion | test_recurrence_calendar_failure_does_not_fail_completion | backend | PASS | — |
| Recurrence — spawn is atomic | test_recurrence_spawn_is_atomic | backend | PASS | — |
| Recurrence — deleting the successor clears the pointer | test_recurrence_deleting_the_successor_clears_the_pointer | backend | PASS | — |
| Recurrence — successor appears in the agenda when due soon | test_recurrence_successor_appears_in_the_agenda_when_due_soon | backend | PASS | — |
| [UI] Today is the default landing tab | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |
| [UI] Today sections and effort totals | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |
| [UI] Today empty state | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |
| [UI] Completing a task updates the list in place | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |
| [UI] Label filter applies to Today | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |
| [UI] Repeat control on create | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |
| [UI] Repeat control hides interval when none | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |
| [UI] Repeat control edit and clear | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |
| [UI] Next-date toast on completing a recurring task | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |
| [UI] Recurring task row shows repeat indicator | tests/ui/today_recurrence.spec.ts (not executed) | UI | MANUAL | Not run: Playwright runs against live DB and mutates saved label filter |

## Test output

```
docker exec atlas-tasktracker-test pytest tests/ -v
collected 77 items
... all 77 tests PASSED (test_agenda 13, test_recurrence 31, plus pre-existing markdown_subtasks, scheduled_status, training_units)
======================== 77 passed, 3 warnings in 7.13s ========================
```
Playwright not executed (see below).

## Failure Analysis

All backend scenarios passed (44 spec scenarios mapped to passing pytest functions; the extra test test_recurrence_create_explicit_null_interval_or_mode_rejected also passed).

MANUAL / untested [UI] scenarios (Playwright tests/ui/today_recurrence.spec.ts exists but was deliberately not run because it runs against the live DB and mutates the user's saved label filter; these need human verification):
- [UI] Today is the default landing tab
- [UI] Today sections and effort totals
- [UI] Today empty state
- [UI] Completing a task updates the list in place
- [UI] Label filter applies to Today
- [UI] Repeat control on create
- [UI] Repeat control hides interval when none
- [UI] Repeat control edit and clear
- [UI] Next-date toast on completing a recurring task
- [UI] Recurring task row shows repeat indicator

## Required Action

Human to verify the [UI] scenarios manually; no code fixes required.
