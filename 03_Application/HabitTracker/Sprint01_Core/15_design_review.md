# Design Review — HabitTracker — Sprint01_Core

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The `.isoformat()` fix from `14_design_corrections.md` is correctly and consistently applied to `period_start`/`period_end` in all three required locations, fully resolving `13_design_review.md`'s Critical finding. However, auditing the same corrected mechanism surfaced a closely related, previously-unaddressed gap: `period_summary`'s `anchor_date` field undergoes the identical str→date type transition as `period_start`/`period_end` (for use in `resolve_report_period`) but was never given the same explicit serialization treatment, and the conversion itself is never declared as a named step. This is a narrow, same-shaped fix, not a redesign.

## Confirmed Problems
1. **`anchor_date`'s str→date conversion is undeclared, and `period_summary.anchor_date`'s JSON-safety is unconfirmed**
   - Severity: Major
   - Location: `10_architecture.json` §`internal_flow` step 10 (`resolve_report_period` signature: `anchor_date: date`) and step 11 (`compute_report`, declared input `anchor_date: str`); §`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract` (Mechanism clause); `10_scaffolding.json` `backend/routers/reports.py` (role text, `get_reports` function, declared arg `anchor_date: str`)
   - Why it is a problem: `resolve_report_period` (step 10) requires `anchor_date` as a `date` object, but `compute_report` (step 11) and the router's `get_reports` function both receive `anchor_date` as a raw query-string `str`. Step 11's text ("Validate period/anchor_date (VALIDATION_ERROR otherwise)... `(period_start, period_end, dates) = resolve_report_period` (step 10)") never names this str→date conversion as an explicit pre-step — unlike `reviews.py`'s `_parse_date_param`, which performs the equivalent job for the date path param but is explicitly scoped "shared by both endpoints in this file only" (i.e. not reusable from `reports.py`). Separately, and more seriously: the just-corrected mechanism text builds `content["period_summary"] = {period, anchor_date, period_start: period_start.isoformat(), period_end: period_end.isoformat(), dates, confirmed_days, elapsed_days}`, applying `.isoformat()` to `period_start`/`period_end` but not to `anchor_date` — even though `anchor_date` undergoes the identical type transition, for the identical reason (passing a typed argument to `resolve_report_period`). The design never states whether the value placed at `content["period_summary"]["anchor_date"]` is the original request string or the `date` object parsed for the `resolve_report_period` call. If an implementer reuses one variable name across both uses (the natural reading of the prose, which refers to "anchor_date" as a single value throughout step 11), the parsed `date` object ends up in `content` after `dataset.model_dump(mode="json")` has already run, reproducing — on a second field, within the same dict literal — precisely the `TypeError`-on-every-call defect that `13_design_review.md`'s Confirmed Problem #1 required removed from `period_start`/`period_end`.
   - Impact: If realized, `GET /reports` would again throw an unhandled 500 on every call, undermining the correction that was just completed. Even under the most charitable implementation (two separately-named variables, chosen correctly), the contract is not self-contained per R-CON-BP-08 — correctness depends on an unstated implementation choice rather than an explicit design decision, and the required str→date conversion itself has no declared home.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the correction re-verified every field it had already identified as a raw `date` (`period_start`/`period_end`) but did not re-audit every other value flowing through the same manually-constructed dict for the identical risk class, even though `anchor_date` undergoes the same type transition for the same reason.

## Recommended Improvements
1. **Orphaned `habit_results` on an archived habit during a Draft day (carried from `11_design_review.md` / `13_design_review.md`)**
   - Location: `00_draft.md` §Defaults and Merging; `10_architecture.json` §`contracts.invariants` (Checked-value rule); §`internal_flow` step 7 (Draft branch)
   - Improvement: Still unaddressed. A Draft day's displayed habit list is always `resolve_active_habits_for_date` (current active window), never "habits with an existing saved row ∪ current active window" — so a habit archived after a checkbox was draft-saved for it silently disappears from the Daily Review screen and from the next PUT's expected set, orphaning its `habit_results` row. Document this as an explicit non-goal, or extend the Draft-branch habit list to the union of active-window habits and habits with an existing saved row for that date.
   - Why: Preserved purely for traceability — correctly scoped as non-blocking across two prior review rounds (rare in a single-user app); not required for approval of this round either.
2. **Shared date-parsing helper for `reports.py`**
   - Location: `10_scaffolding.json` `backend/routers/reports.py` `private_objects` (only `_cell_state` is scaffolded)
   - Improvement: When resolving Confirmed Problem #1's required fix, prefer relocating (or duplicating with a matching name) `reviews.py`'s `_parse_date_param` logic into `backend/review_logic.py` as a canonical shared parser, rather than re-implementing ad hoc string→date parsing a second time in `reports.py`.
   - Why: Keeps the "single canonical implementation, never re-implemented elsewhere" discipline the design already applies to `resolve_active_habits_for_date`/`compute_expected_habit_ids`/`resolve_report_period` consistent for date parsing too.

## Scaffold-Only Observations
1. **No `ColumnSchema` module constants scaffolded (carried from `11_design_review.md` / `13_design_review.md`)**
   - Location: `10_scaffolding.json` `backend/routers/habits.py`, `reviews.py`, `reports.py` `public_objects`
   - Observation: Still absent. Unlike EssayCards' `REVIEW_STATS_SUMMARY_SCHEMA`/`ACTIVITY_SCHEMA` module-level constants, no `HABIT_SCHEMA`/equivalent is scaffolded for any of the three Dataset-returning routers. Row shapes are fully specified in prose (`exposed_surfaces.row_shape`).
   - Impact on implementation: None blocking; adding the constants would keep the stub closer to the module structure the implementer will actually produce.

## Hard Rule Violations
1. **R-CON-AL-03 — Invariant Realizability**
   - Rule Source: `.claude/rules/R-CON-AL.md` (R-CON-AL-03)
   - Location: `10_architecture.json` §`internal_flow` step 11; §`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract` (Mechanism clause)
   - Violation: `period_summary`'s `anchor_date` field is merged into the manually-built `JSONResponse` content dict with no stated serialization treatment, while the parallel `period_start`/`period_end` fields in the same dict literal were just given one in the prior correction round. The design does not state whether `anchor_date` is JSON-safe at the point it is written into `content`, so the response cannot be reliably constructed from the declared steps alone.
   - Required Fix: Explicitly state, at both locations, that the value placed into `content["period_summary"]["anchor_date"]` is the original request string (never the `date` object parsed for the `resolve_report_period` call), or equivalently state an explicit `.isoformat()`/string-conversion step for it — matching the treatment already given to `period_start`/`period_end`. Apply identically to `10_scaffolding.json`'s `reports.py` entry.
2. **R-CON-BP-10 — Input Sufficiency**
   - Rule Source: `.claude/rules/R-CON-BP.md` (R-CON-BP-10)
   - Location: `10_architecture.json` §`internal_flow` step 10 (`resolve_report_period`, requires `anchor_date: date`) and step 11 (`compute_report`, receives `anchor_date: str`)
   - Violation: `resolve_report_period`'s declared signature requires `anchor_date: date`, but `compute_report`'s own declared input is `anchor_date: str`, and its description never names a pre-step performing this conversion — contrast with `reviews.py`'s named, scaffolded `_parse_date_param`, which `reports.py` cannot reuse per that function's own explicit file-local scoping.
   - Required Fix: Add an explicit pre-step (named function or inline instruction) in `internal_flow` step 11 that parses `anchor_date` (str) into a `date` object before calling `resolve_report_period`, mirroring `reviews.py`'s `_parse_date_param` pattern or relocating it into `review_logic.py` as a shared canonical parser (see Recommended Improvements #2).

## Open Uncertainties
1. **Long-term status of the Dataset-plus-sibling-field pattern (carried from `11_design_review.md` / `13_design_review.md`)**
   - Location: `10_architecture.json` §`open_questions[0]`; §`risks` (period_summary risk entry)
   - Uncertainty: Whether `GET /reports` returning `Dataset` plus an additive `period_summary` top-level field is an acceptable pattern long-term, or should be promoted into a versioned platform Dataset extension (R-CON-BP-04 §11).
   - Why it matters: If a future sprint or audit decides this pattern should not be repeated, every app that has copied it needs a coordinated migration. This review round's own finding (Confirmed Problem #1) is additional evidence that the manual-`JSONResponse`-bypass version of this pattern is error-prone to hand-serialize correctly.
   - Suggested owner: Architecture
2. **Future exposure of the reserved `source` column (carried from `11_design_review.md` / `13_design_review.md`)**
   - Location: `10_architecture.json` §`open_questions[1]`
   - Uncertainty: Whether a later sprint adding an automatic result source will need `GET /reviews/{date}` to surface `source` and whether the UI will need a manual-vs-automatic visual distinction.
   - Why it matters: Affects whether this sprint's row shape needs a reserved-but-unexposed field path later, vs. an additive change.
   - Suggested owner: Product

## Minimal Change Set
1. In `10_architecture.json` §`internal_flow` step 11, add an explicit pre-step converting `anchor_date` (str) to a `date` object before calling `resolve_report_period` (step 10), named consistently with `reviews.py`'s `_parse_date_param` pattern.
2. State explicitly, in both the `GET /reports` `ui_contract` Mechanism clause and `internal_flow` step 11, that `content["period_summary"]["anchor_date"]` uses the original request string (not the parsed `date` object) — or, if a parsed value is used instead, apply the same explicit string-conversion step already applied to `period_start`/`period_end`.
3. Apply the identical clarification to `10_scaffolding.json`'s `backend/routers/reports.py` entry (`role` text and `get_reports`'s `returns`/`purpose` fields).

## Approval Condition
`10_architecture.json` §`internal_flow` steps 10–11, the `GET /reports` `ui_contract` Mechanism clause, and `10_scaffolding.json`'s `backend/routers/reports.py` entry must each explicitly declare (a) the str→date conversion step for `anchor_date` before it is passed to `resolve_report_period`, and (b) that `period_summary.anchor_date` is JSON-serializable (either the untouched original string, or an explicit string-conversion applied to it) — closing the same type-safety gap class the prior correction round closed for `period_start`/`period_end`.
