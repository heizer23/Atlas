# Design Review — StorageTracker

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-04-11
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|
| 1 | `10_architecture.json` §interfaces.exposed_surfaces[GET /api/shopping-tasks/views/by_source] vs §internal_flow.step_17 | R-CON-BP-09 (Cross-Artifact Truth Consistency), R-CON-BP-11 (Behavioral Completeness) | Resolve the by_source row shape. exposed_surfaces says "each row has source_tag: str and tasks: list of ShoppingTaskRow" (nested). internal_flow.step_17 says "one row per (task, source_tag) combination" (flat). 10_test_spec.md also describes flat rows. Pick one — the flat model is simpler and consistent with Dataset; adopt it everywhere and remove the nested description. |
| 2 | `10_architecture.json` §shared_views.provides[ShoppingTaskRow] | R-CON-BP-11 (Behavioral Completeness) | ShoppingTaskRow does not include source_tags in the column list (it lists: id, item_id, item_name, status, notes, created_at, completed_at). The by_source view requires source_tag per row and the list endpoint is filtered by source_tag. Add source_tags: list[str] to ShoppingTaskRow definition, consistent with the task table schema. |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json` §contracts.failure_modes | VALIDATION_ERROR covers "invalid field values" but PATCH /shopping-tasks/{id} for an already-closed task (status already done or dismissed) is a distinct case. Consider naming it explicitly as INVALID_STATUS_TRANSITION to aid implementer. |
| 2 | `10_scaffolding.json` §files[shopping_tasks.py].public_objects | `list_shopping_tasks` and `view_by_source` are top-level function entries with a nested `methods[]` array containing themselves — this is structurally redundant (a function duplicated under its own methods list). The implementer should treat these as standalone endpoint functions, not classes. |

## Approval Condition

Resolve the by_source row shape to flat (one row per task×source_tag), update shared_views.provides ShoppingTaskRow to include source_tags, and ensure exposed_surfaces, internal_flow, and test_spec are mutually consistent. No re-review required — corrector may apply changes directly.
