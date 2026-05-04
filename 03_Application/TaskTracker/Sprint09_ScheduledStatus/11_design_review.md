# Design Review — tasktracker

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-05-04
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|
| 1 | `10_test_spec.md` (all scenarios) | R-PRO-BP-01 §5 / reviewer rule: UI files in scaffolding require ≥1 `[UI]` or `[UI — manual]` scenario | `10_scaffolding.json` lists `src/ShellEntry.tsx` as changed; test spec contains no scenario prefixed `[UI]` or `[UI — manual]`. Add at least one UI scenario describing observable user-facing behavior (e.g. Scheduled tab renders with formatted scheduled_at). |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json §deferrals.reviewer` | The "PATCH status=scheduled without scheduled_at" check-existing-row question is surfaced as a deferred decision, which is correct. Implementer should resolve it with the simplest approach: if status=scheduled is in body and scheduled_at is not in model_fields_set, re-fetch the row and validate that scheduled_at is already non-null; return VALIDATION_ERROR if null. This does not require a design change — noting for implementer clarity. |
| 2 | `10_schema.sql` | The schema file contains only the incremental Sprint09 ALTER statements, not the full idempotent schema. This is intentional per the design pattern (schema.sql in the sprint folder is a delta artifact). No change required — the implementer must also update the canonical `schema.sql` in the component root per the deferral list. |

## Approval Condition

Add at least one `[UI — manual]` scenario to `10_test_spec.md` describing an observable user action on the Scheduled tab (e.g. tab renders, row shows formatted scheduled time). The scenario must be prefixed `[UI — manual]` since automated UI test infrastructure is not confirmed in place.
