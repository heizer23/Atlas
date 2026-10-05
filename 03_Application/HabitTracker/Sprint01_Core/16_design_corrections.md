# Design Corrections — HabitTracker — Sprint01_Core

## Applied Changes

1. **Declared the missing `anchor_date` str→date pre-step before `resolve_report_period`**
   - Review Source: `15_design_review.md` §Minimal Change Set item 1; Hard Rule Violation #2 (R-CON-BP-10 — Input Sufficiency)
   - Files Updated: `10_architecture.json` (§`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract` Mechanism clause; §`internal_flow` step 11), `10_scaffolding.json` (`backend/routers/reports.py` `role` text)
   - Change: Both locations now explicitly state that, before calling `resolve_report_period` (step 10), the handler parses the required `anchor_date` query param (str) into `anchor_date_parsed: date` via a file-local `_parse_date_param` helper in `backend/routers/reports.py` (VALIDATION_ERROR if unparseable). This helper is a same-named **duplicate** of `reviews.py`'s private `_parse_date_param` — chosen over relocating a shared parser into `backend/review_logic.py` (the review's Recommended Improvement #2) because duplication is the smaller, non-cross-cutting change: it touches only `reports.py`, leaves `reviews.py` and `review_logic.py` untouched, and `reviews.py`'s `_parse_date_param` is already explicitly scoped file-local, so reuse via import was never an option. `resolve_report_period` is now explicitly called with `anchor_date_parsed`, not the raw string.

2. **Declared that `period_summary.anchor_date` is always the original request string, never the parsed `date` object**
   - Review Source: `15_design_review.md` §Minimal Change Set item 2; Hard Rule Violation #1 (R-CON-AL-03 — Invariant Realizability); Confirmed Problem #1
   - Files Updated: `10_architecture.json` (same two locations as above — `ui_contract` Mechanism clause and `internal_flow` step 11's `content["period_summary"] = {...}` dict-literal text)
   - Change: Picked the simpler of the review's two allowed resolutions (state the original string is used, rather than adding a second `.isoformat()` conversion). Both locations now read `anchor_date: anchor_date (the original, unparsed request string — anchor_date_parsed is used only for the resolve_report_period call and is never written into content)`, closing the ambiguity that let a single reused variable name silently reintroduce the same raw-`date`-in-`JSONResponse` `TypeError` defect the prior correction round (`14_design_corrections.md`) had just removed from `period_start`/`period_end`.

3. **Applied the identical clarification to `10_scaffolding.json`'s `backend/routers/reports.py` entry**
   - Review Source: `15_design_review.md` §Minimal Change Set item 3
   - Files Updated: `10_scaffolding.json` (`backend/routers/reports.py` `role` text; `get_reports` function's `returns` and `purpose` fields; new `_parse_date_param` entry added to `private_objects`)
   - Change: `role` text now states the pre-parse step and that the original `anchor_date` string (not `anchor_date_parsed`) is kept for `period_summary`. `get_reports`'s `returns`/`purpose` fields now state the same two facts (pre-step named, original string preserved). Added a `_parse_date_param` private function entry to `reports.py`'s `private_objects` (mirroring the existing `reviews.py` entry's shape/pattern/`returns`), explicitly noting it is a file-local duplicate and must not be imported cross-file, consistent with `reviews.py`'s own file-local scoping note.

## Unchanged by Design
- All other `internal_flow` steps (1–10, 12–13), all other `exposed_surfaces` entries, `contracts.invariants`/`failure_modes`, `dependencies`, `persistence`, `deferrals`, `risks`, and `open_questions` in `10_architecture.json` are preserved verbatim.
- All other file entries in `10_scaffolding.json` (including `backend/review_logic.py`'s `resolve_report_period` and `reviews.py`'s `_parse_date_param`) are preserved verbatim — no relocation into `review_logic.py` was performed (see Applied Change #1's rationale for why duplication was chosen instead).
- `10_schema.sql` is untouched: `anchor_date` is a query parameter only, never persisted, so no schema-level change was in scope.
- The Recommended Improvements (orphaned `habit_results` on an archived habit; shared date-parsing helper) and Scaffold-Only Observations (no `ColumnSchema` module constants) from `15_design_review.md` were left unaddressed, as instructed — they are explicitly non-blocking.

## Review Alignment Check
- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — `10_architecture.json` §`internal_flow` steps 10–11 and the `GET /reports` `ui_contract` Mechanism clause now both declare (a) the str→date pre-step for `anchor_date` before `resolve_report_period`, and (b) that `period_summary.anchor_date` is JSON-serializable (the untouched original string). `10_scaffolding.json`'s `backend/routers/reports.py` entry states the same.
- Notes: Per the Minimal Change Set's explicit "your choice" framing, duplication (not relocation to `review_logic.py`) was chosen for the `_parse_date_param` pre-step, and "state the original string is used" (not a second `.isoformat()` conversion) was chosen for `anchor_date`'s serialization — both are stated unambiguously in the updated text, so no residual implementer ambiguity remains.
