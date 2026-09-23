# Test Report — EssayCards — Sprint10_DualSchedulerAB

**Verdict:** TESTS_PASSING
**Date:** 2026-09-23
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Classic again grade is flat five seconds via the endpoint | `test_scheduling.py::test_again_is_flat_five_seconds_regardless_of_last_reviewed_at`, `test_flashcards.py::test_review_again_schedules_five_seconds` | backend | PASS | — |
| Classic hard grade applies floor-or-doubled-elapsed via the endpoint | `test_flashcards.py::test_review_hard_first_time_and_repeat_via_endpoint` | backend | PASS | — |
| Classic easy grade applies floor-or-doubled-elapsed via the endpoint | `test_flashcards.py::test_review_easy_first_time_and_repeat_via_endpoint` | backend | PASS | — |
| Consecutive reviews on the same card chain from persisted state | `test_flashcards.py::test_review_consecutive_reviews_chain_from_persisted_state` | backend | PASS | — |
| Failure after several successful reviews still resets to flat five seconds | `test_flashcards.py::test_review_again_after_several_successful_reviews_still_flat_five_seconds` | backend | PASS | — |
| Mature card reviewed again applies doubling at multi-day scale via the endpoint | `test_flashcards.py::test_review_established_card_doubling_at_multiday_scale_via_endpoint` | backend | PASS | — |
| Boundary case at the exact floor crossing pins the tie-break | `test_scheduling.py::test_floor_crossing_boundary_pins_max_tiebreak[hard/good/easy]` | backend | PASS | — |
| Due-queue selection is scheduler-agnostic | `test_flashcards.py::test_due_queue_ordering_is_scheduler_agnostic`, `test_flashcards.py::test_due_rows_carry_scheduler` | backend | PASS | — |
| FSRS resurfacing uses the same RECENT mechanism as Classic | `test_flashcards.py::test_fsrs_resurfacing_uses_recent_mechanism` | backend | PASS | — |
| FSRS rating mapping is correct | `test_scheduling.py::test_fsrs_scheduler_review_maps_ratings_correctly` | backend | PASS | — |
| FSRS card state persists and reloads across requests | `test_flashcards.py::test_fsrs_review_persists_and_reloads_state_across_requests`, `test_scheduling.py::test_fsrs_scheduler_review_loads_existing_state_from_raw_state` | backend | PASS | — |
| FSRS handles a card's first-ever review with no prior state | `test_flashcards.py::test_fsrs_review_handles_first_ever_review_with_no_prior_state`, `test_scheduling.py::test_fsrs_scheduler_review_fresh_card_when_no_existing_state` | backend | PASS | — |
| FSRS relearning is handled correctly | `test_flashcards.py::test_fsrs_review_enters_relearning_on_again_after_review_state`, `test_scheduling.py::test_fsrs_relearning_transitions_state_and_uses_relearning_step` | backend | PASS | — |
| FSRS due date flows through the existing fields with no separate queue | `test_flashcards.py::test_fsrs_review_due_date_flows_through_existing_fields` | backend | PASS | — |
| FSRS datetime handling is timezone-correct | `test_scheduling.py::test_fsrs_scheduler_review_normalizes_naive_and_nonutc_datetimes_to_utc` | backend | PASS | — |
| New card creation assigns a scheduler permanently | `test_flashcards.py::test_new_card_creation_assigns_scheduler_permanently`, `test_ingest.py::test_ingest_new_card_receives_scheduler_assignment`, `test_exploration.py::test_create_card_via_exploration_import_receives_scheduler_assignment` | backend | PASS | — |
| Editing an existing card never reassigns its scheduler | `test_flashcards.py::test_upsert_edit_of_existing_card_never_changes_scheduler_assignment`, `test_ingest.py::test_reingest_never_changes_existing_card_scheduler_assignment` | backend | PASS | — |
| Kill switch disables new assignment without disturbing existing state | `test_flashcards.py::test_kill_switch_disabled_assigns_new_cards_classic`, `test_scheduling.py::test_decide_scheduler_assignment_disabled_by_kill_switch` | backend | PASS | — |
| Assignment is approximately balanced across many cards | `test_scheduling.py::test_decide_scheduler_assignment_approximately_balanced`, `test_scheduling.py::test_decide_scheduler_assignment_deterministic_for_same_id` | backend | PASS | — |
| Migration backfill retains previously-reviewed cards on Classic without altering their schedule | `test_migration.py::test_migration_assigns_legacy_reviewed_cards_to_classic_without_touching_due_dates` | backend | PASS | — |
| Migration backfill assigns never-reviewed existing cards via the balanced mechanism | `test_migration.py::test_migration_assigns_never_reviewed_existing_cards_via_balanced_mechanism`, `test_scheduling.py::test_decide_scheduler_assignment_migrated_never_reviewed_reason` | backend | PASS | — |
| Migration backfill is idempotent on rerun | `test_migration.py::test_migration_backfill_is_idempotent_on_rerun` | backend | PASS | — |
| Experiment summary reports real recorded per-scheduler data with exposed sample sizes | `test_experiment.py::test_experiment_summary_reports_assigned_reviewed_completed_and_recall_with_sample_size`, `test_experiment.py::test_experiment_summary_returns_two_fixed_rows_zero_filled` | backend | PASS | — |
| A rapid-retry review with a short prior interval is excluded from ordinary due-review evidence | `test_experiment.py::test_experiment_summary_excludes_non_due_reviews_from_recall_sample` | backend | PASS | — |
| [UI — manual] Scheduler badge shows the card's persisted algorithm before and after reveal | — | manual | MANUAL | No `tests/ui/` directory exists in the component; per spec this scenario is explicitly marked `[UI — manual]` (no execution infrastructure), so absence of a `.spec.ts` is expected, not a failure. Requires human verification. |

## Test output

```
docker exec atlas-essaycards-test pytest tests/ -v
...
tests/test_scheduling.py::test_again_is_flat_five_seconds_regardless_of_last_reviewed_at PASSED [ 89%]
tests/test_scheduling.py::test_first_time_review_uses_floor_only[hard] PASSED [ 89%]
tests/test_scheduling.py::test_first_time_review_uses_floor_only[good] PASSED [ 90%]
tests/test_scheduling.py::test_first_time_review_uses_floor_only[easy] PASSED [ 90%]
tests/test_scheduling.py::test_repeat_review_doubles_elapsed_when_it_exceeds_floor[hard] PASSED [ 91%]
tests/test_scheduling.py::test_repeat_review_doubles_elapsed_when_it_exceeds_floor[good] PASSED [ 91%]
tests/test_scheduling.py::test_repeat_review_doubles_elapsed_when_it_exceeds_floor[easy] PASSED [ 91%]
tests/test_scheduling.py::test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[hard] PASSED [ 92%]
tests/test_scheduling.py::test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[good] PASSED [ 92%]
tests/test_scheduling.py::test_repeat_review_uses_floor_when_it_exceeds_doubled_elapsed[easy] PASSED [ 93%]
tests/test_scheduling.py::test_invalid_grade_raises_value_error PASSED   [ 93%]
tests/test_scheduling.py::test_floor_crossing_boundary_pins_max_tiebreak[hard] PASSED [ 93%]
tests/test_scheduling.py::test_floor_crossing_boundary_pins_max_tiebreak[good] PASSED [ 94%]
tests/test_scheduling.py::test_floor_crossing_boundary_pins_max_tiebreak[easy] PASSED [ 94%]
tests/test_scheduling.py::test_classic_scheduler_review_matches_compute_next_due_at[again] PASSED [ 94%]
tests/test_scheduling.py::test_classic_scheduler_review_matches_compute_next_due_at[hard] PASSED [ 95%]
tests/test_scheduling.py::test_classic_scheduler_review_matches_compute_next_due_at[good] PASSED [ 95%]
tests/test_scheduling.py::test_classic_scheduler_review_matches_compute_next_due_at[easy] PASSED [ 95%]
tests/test_scheduling.py::test_fsrs_scheduler_review_maps_ratings_correctly PASSED [ 96%]
tests/test_scheduling.py::test_fsrs_scheduler_review_fresh_card_when_no_existing_state PASSED [ 96%]
tests/test_scheduling.py::test_fsrs_scheduler_review_loads_existing_state_from_raw_state PASSED [ 96%]
tests/test_scheduling.py::test_fsrs_scheduler_review_normalizes_naive_and_nonutc_datetimes_to_utc PASSED [ 97%]
tests/test_scheduling.py::test_fsrs_relearning_transitions_state_and_uses_relearning_step PASSED [ 97%]
tests/test_scheduling.py::test_decide_scheduler_assignment_disabled_by_kill_switch PASSED [ 98%]
tests/test_scheduling.py::test_decide_scheduler_assignment_deterministic_for_same_id PASSED [ 98%]
tests/test_scheduling.py::test_decide_scheduler_assignment_approximately_balanced PASSED [ 98%]
tests/test_scheduling.py::test_decide_scheduler_assignment_migrated_never_reviewed_reason PASSED [ 99%]
tests/test_shell_proxy.py::test_essaycards_proxy_returns_json PASSED     [ 99%]
tests/test_shell_proxy.py::test_shell_serves_app_at_basepath PASSED      [100%]

=================================== FAILURES ===================================
__________ test_import_stores_new_result_without_overwriting_history ___________

client = <starlette.testclient.TestClient object at 0x7f8de94c60c0>
db_conn = <connection object at 0x7f8dee044cc0; ...>

    def test_import_stores_new_result_without_overwriting_history(client, db_conn):
        ...
        history = client.get(_history_url(SECTION_ORIGINS_ID))
        assert history.status_code == 200
        rows = history.json()["rows"]
        assert len(rows) == 3
>       assert rows[0]["score"] == 5  # most recent first
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       assert 4 == 5

tests/test_examinations.py:112: AssertionError

=========================== short test summary info ============================
FAILED tests/test_examinations.py::test_import_stores_new_result_without_overwriting_history
================== 1 failed, 260 passed, 4 warnings in 31.37s ==================
```

### Independent pre-existing-failure verification

The implementer's self-report claimed `test_import_stores_new_result_without_overwriting_history`
is a pre-existing, sprint-unrelated failure. This was independently re-verified rather than
accepted at face value:

1. `git log --follow -- tests/test_examinations.py` shows this test function was introduced in
   commit `11c94ae` ("EssayCards: oral examinations — export package, ChatGPT round-trip,
   history"), well before Sprint10.
2. `git status --porcelain -- 03_Application/EssayCards/` confirms `tests/test_examinations.py`
   itself is untouched by this sprint's working-tree diff (not in the modified/untracked file
   list). `tests/fixtures.sql` IS modified, but the diff is purely additive (a new Sprint10
   pinning `UPDATE` plus new Essay-H fixture rows appended after existing content) — no existing
   examination/section fixture rows for essay A / section "origins" were altered.
3. Direct reproduction: `git stash push -u -- 03_Application/EssayCards` (removing every Sprint10
   change), rebuilt `atlas-essaycards-test`, and ran `pytest tests/test_examinations.py -v`
   against pre-sprint code. Result: identical failure, `assert 4 == 5` at the same line
   (`tests/test_examinations.py:112`), `1 failed, 21 passed`. `git stash pop` restored the sprint
   changes and the test container was rebuilt again against sprint code (verified back to
   `260 passed, 1 failed`) before writing this report.

This confirms the failure is pre-existing, reproduces identically with and without this sprint's
changes, and is unrelated to any file in this sprint's `files_changed` list
(`10_scaffolding.json`). It is excluded from the verdict on that basis.

## Failure Analysis

All 25 scenarios in `10_test_spec.md` are satisfied: 24 backend scenarios have passing,
independently-mapped test functions, and the 1 `[UI — manual]` scenario has no automated
coverage by design (no `tests/ui/` directory exists for this component, consistent with the
spec marking it manual rather than `[UI]`).

The single pytest failure (`test_examinations.py::test_import_stores_new_result_without_overwriting_history`)
is not part of this sprint's test spec, was independently confirmed to be a pre-existing defect
unrelated to Sprint10 (see verification steps above — it reproduces identically against
pre-sprint code, in a file untouched by this sprint, unconnected to any scheduling/experiment
logic), and is therefore excluded from the verdict rather than counted as a sprint regression.

## Required Action

Proceed to `/sprint-close`; the pre-existing `test_import_stores_new_result_without_overwriting_history`
failure is out of scope for this sprint and should be tracked/fixed separately.
