# Design Review — HabitTracker — Sprint01_Core

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The correction in `12_design_corrections.md` fully resolves `11_design_review.md`'s blocking issue — the `period_summary` attachment mechanism for `GET /reports` is now explicitly named in all three required locations. However, naming the mechanism in code-level detail surfaced a new, concrete defect in that same mechanism: two of `period_summary`'s fields are raw `datetime.date` objects that bypass `Dataset.model_dump()`'s serialization and will raise `TypeError` in Starlette's default JSON encoder on every call. This is a narrow, mechanical fix, not a redesign.

## Confirmed Problems
1. **`period_summary.period_start`/`period_end` are not JSON-serializable under the specified attachment mechanism**
   - Severity: Critical
   - Location: `10_architecture.json` §`internal_flow` step 11 (`compute_report`); §`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract` (Mechanism clause); `10_scaffolding.json` `backend/routers/reports.py` (`role` text and `get_reports`'s `returns`/`purpose`)
   - Why it is a problem: Step 10 explicitly types `resolve_report_period`'s output as `period_start: date, period_end: date, dates: list[str]` — `dates` is deliberately pre-stringified but `period_start`/`period_end` are left as raw Python `datetime.date` objects (consistent with their use as bind parameters in step 11's `habit_rows` query: `WHERE active_from <= period_end AND (end_date IS NULL OR end_date >= period_start)`, which needs real `date` values). Step 11 and the `ui_contract` Mechanism clause then build `content["period_summary"] = {period, anchor_date, period_start, period_end, dates, confirmed_days, elapsed_days}` directly from these same variables and hand `content` straight to `JSONResponse(content=content)`. `content = dataset.model_dump(by_alias=True, mode="json")` only converts the pydantic `Dataset` object's own fields (`meta`/`schema`/`rows`) to JSON-safe values — the `period_summary` key is inserted into the plain dict *after* that call, so it never passes through pydantic's serializer. Starlette's `JSONResponse.render()` calls the stdlib `json.dumps()` with no custom encoder, which raises `TypeError: Object of type date is not JSON serializable` for a raw `date` value.
   - Impact: Every call to `GET /api/habittracker/reports` — the core endpoint of the Reports screen, the third of this sprint's three scoped screens — throws an unhandled exception (500) at the exact point the correction just finished specifying in code-level detail. This is not an edge case; it reproduces on every invocation, for every period.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the correction fully specified the structural *attachment* of `period_summary` (bypassing `Dataset`'s constructor, using `response_model=None` + manual `JSONResponse`) but did not re-derive what that bypass costs: once a value leaves the `Dataset.model_dump(mode="json")` pipeline, nothing else in the chain converts non-JSON-native Python types to strings.

## Recommended Improvements
1. **Precision of the "same mechanism as EssayCards" claim**
   - Location: `10_architecture.json` §`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract`; `10_scaffolding.json` `backend/routers/reports.py` role text
   - Improvement: Both artifacts state this is "the identical ... mechanism EssayCards already uses in `backend/routers/review_stats.py::get_review_stats_summary`." Checked directly: `review_stats.py`'s `_dataset_response()` helper (`JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))`) demonstrates the `response_model=None` + `model_dump()` + `JSONResponse` pattern, but none of its three endpoints ever merges an additional top-level sibling key into `content` — all of them return a pure Dataset. The dict-merge-a-sibling-field technique itself has no precedent in that file. Rephrase to credit the precedent only for the parts it actually demonstrates (bypassing `response_model` validation/stripping via manual `JSONResponse`), and treat the sibling-field dict-merge plus its date-serialization requirement as this design's own addition.
   - Why: An implementer who opens `review_stats.py` expecting to find the sibling-field pattern reproduced there will not find it, and may copy its date-handling (all dates are pre-stringified in SQL via `to_char(...)`) without noticing `period_start`/`period_end` are the one place this design diverges from that pattern.
2. **Orphaned `habit_results` on an archived habit during a Draft day (carried from `11_design_review.md` Non-Blocking Issue #1)**
   - Location: `00_draft.md` §Defaults and Merging; `10_architecture.json` §`contracts.invariants` (Checked-value rule); §`internal_flow` step 7 (Draft branch)
   - Improvement: Still unaddressed in the corrected artifacts. A Draft day's displayed habit list is always `resolve_active_habits_for_date` (current active window), never "habits with an existing saved row ∪ current active window" — so a habit archived after a checkbox was draft-saved for it silently disappears from the Daily Review screen and from the next PUT's expected set, orphaning its `habit_results` row. Document this as an explicit non-goal, or extend the Draft-branch habit list to the union of active-window habits and habits with an existing saved row for that date.
   - Why: Preserved purely for traceability — the first review correctly scoped this as non-blocking (rare in a single-user app) and it was explicitly left untouched by the correction, which is appropriate; it is not required for approval of this round.

## Scaffold-Only Observations
1. **No `ColumnSchema` module constants scaffolded (carried from `11_design_review.md` Non-Blocking Issue #2)**
   - Location: `10_scaffolding.json` `backend/routers/habits.py`, `reviews.py`, `reports.py` `public_objects`
   - Observation: Still absent. Unlike EssayCards' `REVIEW_STATS_SUMMARY_SCHEMA`/`ACTIVITY_SCHEMA` module-level constants, no `HABIT_SCHEMA`/equivalent is scaffolded for any of the three Dataset-returning routers. Row shapes are fully specified in prose (`exposed_surfaces.row_shape`), so this does not block implementation.
   - Impact on implementation: None blocking; adding the constants would keep the stub closer to the module structure the implementer will actually produce.

## Hard Rule Violations
1. **R-CON-AL-03 — Invariant Realizability**
   - Rule Source: `.claude/rules/R-CON-AL.md` (R-CON-AL-03)
   - Location: `10_architecture.json` §`internal_flow` step 11; §`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract`
   - Violation: The declared `GET /reports` response (Dataset + `period_summary`) depends on an unspecified formatting/derivation step — converting `period_start`/`period_end` from `date` objects to JSON-serializable strings — that is nowhere declared in the contract. As written, the response cannot actually be constructed without an implementer independently discovering and adding this conversion.
   - Required Fix: State explicitly, at both locations, that `period_start` and `period_end` must be rendered as `YYYY-MM-DD` strings (e.g., `.isoformat()`) before being placed into `content["period_summary"]`, or that the final `content` dict is passed through `fastapi.encoders.jsonable_encoder()` before `JSONResponse(content=content)`. Apply the same correction to `10_scaffolding.json`'s `backend/routers/reports.py` entry.

## Open Uncertainties
1. **Long-term status of the Dataset-plus-sibling-field pattern**
   - Location: `10_architecture.json` §`open_questions[0]`; §`risks` (period_summary risk entry)
   - Uncertainty: Whether `GET /reports` returning `Dataset` plus an additive `period_summary` top-level field is an acceptable pattern long-term, or should be promoted into a versioned platform Dataset extension (R-CON-BP-04 §11). Already correctly surfaced with an owner in the design per R-OPS-BP-01; not re-litigated as blocking in this review, consistent with `11_design_review.md`'s treatment.
   - Why it matters: If a future sprint or audit decides this pattern should not be repeated, every app that has copied it (now potentially including HabitTracker) needs a coordinated migration.
   - Suggested owner: Architecture
2. **Future exposure of the reserved `source` column**
   - Location: `10_architecture.json` §`open_questions[1]`
   - Uncertainty: Whether a later sprint adding an automatic result source will need `GET /reviews/{date}` to surface `source` and whether the UI will need a manual-vs-automatic visual distinction.
   - Why it matters: Affects whether this sprint's row shape needs a reserved-but-unexposed field path later, vs. an additive change.
   - Suggested owner: Product

## Minimal Change Set
1. In `10_architecture.json` §`internal_flow` step 11, state explicitly that `period_start`/`period_end` are converted to `YYYY-MM-DD` strings (or passed through `jsonable_encoder`) before being merged into `content["period_summary"]`.
2. Apply the identical clarification to `10_architecture.json` §`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract` (Mechanism clause).
3. Apply the identical clarification to `10_scaffolding.json`'s `backend/routers/reports.py` entry (`role` text and `get_reports`'s `returns`/`purpose` fields).

## Approval Condition
`10_architecture.json` §`internal_flow` step 11, the `GET /reports` `ui_contract` Mechanism clause, and `10_scaffolding.json`'s `backend/routers/reports.py` entry must each state the explicit string-conversion (or `jsonable_encoder`) step that makes `period_summary.period_start`/`period_end` JSON-serializable before being merged into the manually constructed `JSONResponse`, so `GET /api/habittracker/reports` does not throw on every call as currently specified.
