# Design Review — tasktracker — Sprint11_TodayAndRecurrence

**Verdict:** APPROVED
**Date:** 2026-10-30
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change | Likely Cause (Design Phase) |
|---|----------|--------------------------|-----------------|-----------------------------|

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json` risks[0] / open_questions[0]; invariant "Effective date (agenda)" | The draft's literal effective-date rule combined with the existing auto-promotion (`tasks.py` `_run_auto_promotion`: `scheduled_at <= current_date` becomes `in_progress`) means a task scheduled for today with no `due_date` never appears in Today or Overdue. The designer surfaced this and assigned it to product, and the design is implementable as written. Recommend the human settle it before implementation. Reversing it later changes the expression in step 9 and the two scenarios "Agenda — non-scheduled status uses due_date" and "Agenda — auto-promotion runs before the query and persists" in `10_test_spec.md`. |
| 2 | `10_architecture.json` internal_flow steps 10 and 11(2); `src/ShellEntry.tsx` ~L922 (edit form sends `scheduled_at: null` unless status is scheduled) | A promoted recurring fixed task with only `scheduled_at` (no `due_date`) is `in_progress`. Any edit-form save sends `scheduled_at: null`, so merged-state validation rejects the save with "fixed requires a date". Completing the same task differs by path. The edit form falls back to the snapshot only when `pre.status == 'scheduled'`. The status toggle keeps the retained `scheduled_at`, so it yields a scheduled successor. Neither outcome is wrong enough to block, but the implementer should treat both as known behavior, not a bug. `10_test_spec.md` has no scenario for either. |
| 3 | `10_architecture.json` PATCH surface (`due_date` explicit null now clears) | The backend semantics are defined. The cleared-state UI payload is not stated, which matters under R-CON-AL-05. The existing edit form already sends `due_date: dueDate \|\| null` (`ShellEntry.tsx:929`), so the round trip works without a frontend change. Side effect: cleared dates in the edit form, which were silently ignored before, now persist. This is the intended fix and is covered by the scenario "Recurrence — due_date explicit null clears on a normal task". |
| 4 | `10_scaffolding.json` TaskCreate (`recurrence_interval: int`, `recurrence_mode: str`) vs `10_architecture.json` failure_modes (explicit null interval/mode is VALIDATION_ERROR) | On POST the fields are non-optional types. An explicit null would be rejected by Pydantic before the handler runs, so the error code depends on the platform handler's mapping. The PATCH case is covered by tests. The POST case is untested. The implementer should confirm the code is VALIDATION_ERROR and add a case if cheap. |
| 5 | `10_architecture.json` risks[6] / deferred_decisions | Moving Active to `/tasks/active` makes `/tasks` and any unknown `/tasks/<x>`, including the Sprint10 calendar-description deep links, land on Today. This is already disclosed and deferred. No action is needed now. |

## Approval Condition

None — approved as-is.
