# Design Corrections — HabitTracker

## Applied Changes

1. **`period_start`/`period_end` JSON-serialization fix (R-CON-AL-03, Critical)**
   - Review Source: `13_design_review.md` §Confirmed Problems #1, §Hard Rule Violations #1, §Minimal Change Set
   - Files Updated: `10_architecture.json`, `10_scaffolding.json`
   - Change: Chose `.isoformat()` string conversion (not `jsonable_encoder()`) as the single mechanism, applied consistently across all three required locations:
     1. `10_architecture.json` §`internal_flow` step 11 (`compute_report`) — the description now states explicitly that `period_start`/`period_end` (raw `datetime.date` objects from step 10) must be converted via `.isoformat()` before being placed into `content["period_summary"]`, with the reasoning (they are merged into `content` after `model_dump(mode="json")` runs and so never pass through pydantic's serializer; Starlette's `JSONResponse.render()` uses stdlib `json.dumps()` with no custom encoder and raises `TypeError` on a raw `date`).
     2. `10_architecture.json` §`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract` Mechanism clause — identical clarification added, including the corrected `content["period_summary"] = {..., period_start: period_start.isoformat(), period_end: period_end.isoformat(), ...}` construction.
     3. `10_scaffolding.json` `backend/routers/reports.py` entry — `role` text updated with the identical `.isoformat()` clarification and corrected dict construction; `get_reports`'s `returns` field now states the output's `period_start`/`period_end` are `.isoformat()` strings, never raw `date` objects; `purpose` field states the conversion step and why it is required (R-CON-AL-03).

2. **Precision of the "identical mechanism as EssayCards" claim (Recommended Improvement #1, non-blocking)**
   - Review Source: `13_design_review.md` §Recommended Improvements #1
   - Files Updated: `10_architecture.json` (internal_flow step 11; `GET /reports` `.ui_contract`), `10_scaffolding.json` (`backend/routers/reports.py` role text)
   - Change: Reworded the claim, in the same three locations already being edited for the Critical fix, from "identical/same mechanism as EssayCards' `review_stats.py::get_review_stats_summary`" to crediting the precedent only for what it actually demonstrates — the `response_model=None` + `model_dump()` + `JSONResponse` bypass pattern via `review_stats.py`'s `_dataset_response()` helper — while explicitly noting that helper never merges a sibling key into the dict and never needed date-formatting (its dates are pre-stringified via SQL `to_char()`). The sibling-field merge and the date-conversion step are now stated as this design's own addition, not reused from that precedent. No new locations were touched for this change; it was folded into edits already required by item 1.

## Unchanged by Design
- No other section of `10_architecture.json` or `10_scaffolding.json` was modified. `00_draft.md` and `10_schema.sql` were not touched (the review's Minimal Change Set did not reference them; this fix is purely a response-construction detail inside the `reports.py` route, not a schema or domain-model change).
- Non-blocking issue #2 (orphaned `habit_results` on an archived habit during a Draft day) and Scaffold-Only Observation #1 (no `ColumnSchema` module constants) were explicitly carried-forward/non-blocking per the review and were left untouched, per the review's own instruction not to re-litigate them.
- `open_questions`, `risks`, `deferrals`, and all other `contracts`/`interfaces` entries not naming the `GET /reports` endpoint's `period_summary` mechanism were preserved verbatim.

## Review Alignment Check
- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — `10_architecture.json` §`internal_flow` step 11, the `GET /reports` `ui_contract` Mechanism clause, and `10_scaffolding.json`'s `backend/routers/reports.py` entry each now state the explicit `.isoformat()` string-conversion step that makes `period_summary.period_start`/`period_end` JSON-serializable before being merged into the manually constructed `JSONResponse`.
- Notes: None — a single mechanism (`.isoformat()`) was chosen and applied consistently across all three locations, as required. No conflicts with `00_draft.md` were encountered.
