# Design Corrections — HabitTracker

## Applied Changes

1. **Named the explicit technical mechanism for attaching `period_summary` to `GET /api/habittracker/reports`**
   - Review Source: `11_design_review.md` — Blocking Issue #1 / Approval Condition
   - Files Updated: `10_architecture.json`, `10_scaffolding.json`
   - Change: The design previously stated that `GET /reports` returns a `Dataset` "PLUS one additive top-level sibling field" (`period_summary`) without specifying how that field is attached to the response, risking an implementer passing it as a `Dataset(...)` constructor kwarg (silently dropped, since `platform_contracts.Dataset` has no `extra="allow"`). Adopted the working precedent from `03_Application/EssayCards/backend/routers/review_stats.py::get_review_stats_summary` and named it explicitly in three places:
     - `10_architecture.json` §`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract` — added a "Mechanism" clause naming `response_model=None` + `dataset.model_dump(by_alias=True, mode="json")` + dict-merge + `JSONResponse(content=content)`, with an explicit cross-reference to the EssayCards precedent file.
     - `10_architecture.json` §`internal_flow` step 11 (`compute_report`) — the description now ends by spelling out the exact mechanism (building the `Dataset` as usual, then `content = dataset.model_dump(...)`, `content["period_summary"] = {...}`, `return JSONResponse(content=content)`, route declares `response_model=None`) instead of ending at "return as the additive Dataset response."
     - `10_scaffolding.json` `backend/routers/reports.py` — the `role` text and the `get_reports` function's `returns`/`purpose` fields now state the same mechanism (route decorator, `model_dump`, dict-merge, `JSONResponse`, `response_model=None`), with the same cross-reference to EssayCards' `review_stats.py` and its `_dataset_response` helper idiom.
   - No change to `query_behavior.row_shape` text was needed beyond what was already present — `row_shape` already fully specified `period_summary`'s field-level shape; what was missing was the attachment mechanism, now covered by `ui_contract` and `internal_flow` step 11.

## Unchanged by Design

- All other `10_architecture.json` sections (classification, all other contracts/invariants/failure_modes, all other `exposed_surfaces` entries, `internal_flow` steps 1–10 and 12–13, `dependencies`, `persistence`, `deferrals`, `risks`, `open_questions`) are preserved verbatim.
- All other `10_scaffolding.json` entries (every other file's `role`/`public_objects`/`private_objects`, `nginx_note`, `main_tsx_note`, `env_vars`, `route_registration_note`) are preserved verbatim.
- `10_schema.sql` was not touched — the review's blocking issue does not involve persistence/schema, and no other artifact required a schema-consistency fix as a result of this correction.
- The three Non-Blocking Issues from the review (orphaned `habit_results` on archived-habit draft edge case; missing `ColumnSchema` module constants in the scaffold; `open_questions` framing) were left untouched — they are explicitly informational per the review and not required before implementation.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: None — the correction is narrowly scoped to naming the attachment mechanism in the two locations the Approval Condition names (`internal_flow` step 11, `reports.py` scaffold entry), plus the adjacent `ui_contract` field at the same endpoint (also listed in the Blocking Issue's Location column) for R-CON-BP-08 self-containment. No new files, abstractions, or scope were introduced.
