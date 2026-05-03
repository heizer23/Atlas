# Design Review — Notifications — Sprint01_Immediate_Notify

**Verdict:** APPROVED
**Date:** 2026-04-15
**Reviewer:** sprint_design_reviewer

## Blocking Issues

_(None)_

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json` § internal_flow step 4 vs time_authority | Step 4 captures `dispatched_at = datetime.now(UTC)` before the FCM call (step 5), but `time_authority` says the value is "captured after successful FCM send() call." The `schema_notes.dispatched_at_column` resolves this by clarifying the in-memory value is used regardless. Implementer should capture `dispatched_at` after step 5 (after FCM succeeds) to match the declared time_authority. No design change required — implementer discretion is sufficient. |
| 2 | `10_scaffolding.json` § route_ordering_note | Correctly flags that `POST /notifications/send` must be registered before `POST /notifications/{notification_id}/replace`. Implementer must verify order in the final file. This is noted in scaffolding but not enforced by a test scenario — acceptable for a platform-internal concern. |

## Design Strengths

- Endpoint is minimal and contracts are fully specified: request fields, response fields, error codes, status codes, and null semantics are all explicit.
- NULL `fire_at` semantics for immediate-send rows are correctly analyzed — the dispatch job WHERE clause safely ignores NULL rows with no code change.
- FCM token invariants (never logged, never in response) are carried forward from the existing module contract.
- `no_db_write_on_fcm_failure` contract is explicit and testable — the test spec covers it.
- Schema migration is backward-safe: existing NOT NULL rows are unaffected; DEFAULT '' guards against accidental NULL insertion for label/deep_link.
- Layer classification is correct: this is a platform capability (generic push dispatch) with no domain logic embedded.
- R-CON-PL-01 compliance: the endpoint exposes a technical capability (immediate FCM dispatch) without encoding application-specific workflow decisions. `source` field is opaque to the platform.
- R-CON-BP-11 compliance: all interface cases (success, no device, FCM failure, validation error) map to internal_flow branches.
- Test spec covers all five observable behaviors including the no-DB-write-on-FCM-failure invariant.

## Approval Condition

None — approved as-is. The non-blocking observations are resolved within existing design text (schema_notes) and implementation notes; no artifact changes are required before implementation proceeds.
