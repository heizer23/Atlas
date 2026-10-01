# Test Report — EssayCards — Sprint12_FSRSAndUXOverhaul

**Verdict:** TESTS_PASSING
**Date:** 2026-10-01
**Fix iteration:** 1

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| FSRS is the only scheduler for a new card | `test_ingest_new_card_has_no_scheduler_metadata`, `test_new_card_creation_has_no_scheduler_metadata`, `test_create_card_via_exploration_import_has_no_scheduler_metadata` | backend | PASS | — |
| A review updates the due date through FSRS | `test_fsrs_review_due_date_flows_through_existing_fields`, `test_fsrs_review_persists_and_reloads_state_across_requests` | backend | PASS | — |
| Due-queue selection and ordering are unaffected by the scheduler change | `test_due_queue_ordering_unaffected_by_scheduler_removal` (+ full due-ordering suite) | backend | PASS | — |
| Migration backfill preserves due dates and review history for a legacy-reviewed card | `test_legacy_fsrs_backfill_creates_state_for_reviewed_card_without_one` | backend | PASS | — |
| Migration backfill is safe to rerun | `test_legacy_fsrs_backfill_is_idempotent_on_rerun` | backend | PASS | — |
| Migration backfill skips a card that already has native FSRS state | `test_legacy_fsrs_backfill_skips_card_that_already_has_state` | backend | PASS | — |
| Scheduling data is backed up before destructive migration | `test_backup_table_snapshots_pre_migration_scheduler_data_once` | backend | PASS | — |
| The dual-scheduler experiment is fully removed | `test_experiment_summary_route_is_fully_removed` | backend | PASS | — |
| Essay with zero cards never satisfies the card milestones | `test_essay_with_zero_cards_has_card_milestones_false_and_level_bounded_by_exam_milestones` | backend | PASS | — |
| All cards seen and future-safe satisfies both card milestones | `test_essay_all_cards_seen_and_future_safe_satisfies_card_milestones` | backend | PASS | — |
| One unseen card keeps the cards-seen milestone false | `test_essay_one_unseen_card_fails_cards_seen_milestone` | backend | PASS | — |
| Guided-passed requires every section to individually meet the threshold | `test_essay_guided_passed_requires_every_section_at_or_above_threshold` | backend | PASS | — |
| Guided and unguided milestones are independent | `test_essay_guided_and_unguided_milestones_are_independent` | backend | PASS | — |
| learning_level sums the four milestones regardless of which ones are true | `test_essay_learning_level_sums_four_independent_milestones_in_any_order` | backend | PASS | — |
| Essay detail carries the same learning-progress fields as the list | `test_get_essay_detail_carries_same_learning_progress_fields_as_list` | backend | PASS | — |
| Essay status is unaffected by this sprint | `test_essay_status_unaffected_by_learning_progress_changes` | backend | PASS | — |
| Examination package requires a valid exam_type | `test_examination_package_requires_exam_type_query_param` | backend | PASS | — |
| Unguided examination package never includes calibration context | `test_examination_package_unguided_never_includes_last_examination` | backend | PASS | — |
| Guided examination package uses only guided history for calibration | `test_examination_package_guided_uses_only_guided_history_for_calibration` | backend | PASS | — |
| Importing examination results requires exam_type on every result | `test_import_examinations_requires_exam_type_per_result` | backend | PASS | — |
| Importing examination results rejects an invalid exam_type value | `test_import_examinations_rejects_invalid_exam_type_value` | backend | PASS | — |
| Section examination history shows exam_type | `test_section_examinations_history_includes_exam_type` | backend | PASS | — |
| Review activity endpoint is zero-filled over a fixed 30-day window | `test_activity_returns_thirty_zero_filled_utc_days`, `test_activity_counts_reviews_on_the_correct_utc_day` | backend | PASS | — |
| Review intervals endpoint sums to the total scheduled card count | `test_intervals_returns_six_zero_filled_buckets_summing_to_total_scheduled` | backend | PASS | — |
| Every pre-existing button/action remains reachable after consolidation | `button_nav_inventory.spec.ts` (4 tests: overview page actions, essay-header ActionMenu, section-end ActionMenu + examination history, desktop nav regrouping) | UI | PASS | — |
| [UI] Category collapse control hides and restores essay rows, and its state survives a reload | `tests/ui/category_collapse.spec.ts` | UI | PASS | — |
| [UI] Essay header action menu exposes Study and both oral exam variants without a cluttered button row | `tests/ui/essay_action_menu.spec.ts` | UI | PASS | — |
| [UI] Learning-level badge shows a tooltip naming all four milestones | `tests/ui/learning_level_badge.spec.ts` (2 tests) | UI | PASS | — |

## Test output

```
$ docker exec atlas-essaycards-test pytest tests/ -v
...
tests/test_essays.py ... (36 tests) ... all PASSED
tests/test_examinations.py ... (29 tests) ... all PASSED
tests/test_exploration.py ... (29 tests) ... all PASSED
tests/test_flashcards.py ... (56 tests) ... all PASSED
tests/test_images.py ... (16 tests) ... all PASSED
tests/test_ingest.py ... (18 tests) ... all PASSED
tests/test_ingest_endpoint.py ... (18 tests) ... all PASSED
tests/test_migration.py ... (9 tests) ... all PASSED
  tests/test_migration.py::test_backup_table_snapshots_pre_migration_scheduler_data_once PASSED
  tests/test_migration.py::test_scheduler_columns_are_dropped_from_flashcard_review_state_and_review_events PASSED
  tests/test_migration.py::test_experiment_summary_route_is_fully_removed PASSED
  tests/test_migration.py::test_legacy_fsrs_backfill_creates_state_for_reviewed_card_without_one PASSED
  tests/test_migration.py::test_legacy_fsrs_backfill_skips_card_that_already_has_state PASSED
  tests/test_migration.py::test_legacy_fsrs_backfill_is_idempotent_on_rerun PASSED
  tests/test_migration.py::test_legacy_fsrs_backfill_already_ran_against_fixture_card_via_startup PASSED
  tests/test_migration.py::test_exam_type_column_defaults_pre_sprint_rows_to_guided PASSED
  tests/test_migration.py::test_estimate_initial_fsrs_state_still_importable_and_pure PASSED
tests/test_nuggets.py ... (16 tests) ... all PASSED
tests/test_questions.py ... (19 tests) ... all PASSED
tests/test_review_stats.py ... (10 tests) ... all PASSED
tests/test_scheduling.py ... (11 tests) ... all PASSED
tests/test_shell_proxy.py ... (3 tests) ... all PASSED

======================= 267 passed, 4 warnings in 58.41s =======================
```

```
$ docker exec atlas-playwright npx playwright test 03_Application/EssayCards/tests/ui/ \
    --config=02_Platform/Atlas_Shell/playwright.config.ts --reporter=list

Running 11 tests using 3 workers

  ✓  1 button_nav_inventory.spec.ts:25:5 › overview page exposes every pre-existing page-level and category-level action (491ms)
  ✓  2 category_collapse.spec.ts:34:5 › category collapse toggle hides essay rows, keeps heading visible, and persists across reload (741ms)
  ✓  3 essay_action_menu.spec.ts:21:5 › essay header exposes a primary action plus a secondary action menu, no cluttered button row (834ms)
  ✓  4 learning_level_badge.spec.ts:16:5 › learning-level badge on the overview row exposes an accessible explanation of all four milestones (399ms)
  ✓  5 button_nav_inventory.spec.ts:46:5 › essay header action menu exposes every pre-existing essay-level action (665ms)
  ✓  6 review_stats.spec.ts:19:5 › Stats nav entry navigates to the stats page (416ms)
  ✓  7 learning_level_badge.spec.ts:36:5 › learning-level badge is also present on the essay header (594ms)
  ✓  8 review_stats.spec.ts:28:5 › stats page renders five zones in order, forecast and observed recall clearly distinguished (561ms)
  ✓  9 button_nav_inventory.spec.ts:98:5 › section-end action menu and examination history remain reachable after consolidation (680ms)
  ✓  10 button_nav_inventory.spec.ts:145:5 › desktop nav reflects the Sprint12 regrouping — Experiment removed, Add / Update Essay retained (266ms)
  ✓  11 review_stats.spec.ts:52:5 › Observed recall zone shows Day, Week, Month cards with recall rate and grade breakdown (610ms)

  11 passed (3.1s)
```

## Failure Analysis

All 267 backend pytest functions and all 11 Playwright UI specs pass — zero FAIL, zero MISSING. The two
coverage gaps identified in fix iteration 0 are now closed:

1. **"The dual-scheduler experiment is fully removed"** — `tests/test_migration.py::
   test_experiment_summary_route_is_fully_removed` now asserts `GET /api/essaycards/experiment/summary`
   returns 404.

2. **"Every pre-existing button/action remains reachable after consolidation"** — the new
   `tests/ui/button_nav_inventory.spec.ts` (4 tests) walks the full `§button_nav_inventory` list:
   overview page-level actions (Images / Import exam results / Import exploration / Due for review)
   plus per-category Study; the essay-header `ActionMenu` (primary Study/Question-overview, Guided oral
   exam, Unguided oral exam, Export essay/Import, + New nugget); the section-end `ActionMenu` (Review
   this section, Export section/Import, Insert section after/Import) plus `SectionExaminationHistory`;
   and the desktop nav regrouping (Experiment entry removed, Add / Update Essay retained).

All scenarios passed.

## Required Action

None — sprint is ready for `/sprint-close`.
