# Design Review — TaskTracker / Sprint10_CalendarBlocker

**Verdict:** APPROVED
**Date:** 2026-05-04
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_scaffolding.json` — `_sync_calendar_event` args | `scheduled_at: date | None` is listed for all three actions but `delete` does not use it. Minor signature noise; implementer should accept and ignore it for `delete`, or split the signature. Non-blocking. |
| 2 | `10_architecture.json` — `internal_flow.step 4` | "scheduled_at or title changed" detection requires reading `title` from the pre-update snapshot. The pre-update snapshot SELECT in the existing code only fetches `status, completed_at, scheduled_at`. Implementer must expand the snapshot SELECT to include `title` and `description`. Architecture defers this to `deferrals.application_implementer` ("Ensure scheduled_at is available...") — clear enough, but the snapshot column list gap is implicit. Recommend the implementer note verify the SELECT is extended. |
| 3 | `10_test_spec.md` — "Patch scheduled task with same scheduled_at and same title — no calendar update" | This scenario is valuable but depends on the pre-snapshot comparison logic being implemented correctly. No spec issue; reviewer note for test writer that this scenario requires mock-verifying the CalendarConnector is NOT called (negative assertion). |

## Approval Condition

None — approved as-is. No blocking issues. The design is minimal, contract-first, correctly layered, best-effort semantics are explicit throughout, and all required artifacts are present. Implementer should pay attention to expanding the pre-update snapshot SELECT to include `title` and `description` for the update-branch detection.
