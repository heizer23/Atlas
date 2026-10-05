# Design Review — HabitTracker — Sprint01_Core

## Verdict
- Status: APPROVED
- Summary: `16_design_corrections.md` correctly closes the last open gap (`anchor_date`'s str→date pre-step and its JSON-safety) from `15_design_review.md`. This round re-audited all seven `period_summary` fields individually (`period`, `anchor_date`, `period_start`, `period_end`, `dates`, `confirmed_days`, `elapsed_days`) for JSON-safety and found every one now has an explicit, unambiguous, individually-stated treatment or is natively JSON-safe by declared type with no undeclared parallel variable. No new Critical/Major defect was found in this round, in this area or elsewhere. The design is approved.

## Confirmed Problems
None identified.

**Field-by-field verification of `content["period_summary"]` (per this review's specific mandate), `10_architecture.json` §`internal_flow` step 11 / §`interfaces.exposed_surfaces` "GET /api/habittracker/reports" `.ui_contract` Mechanism clause:**

| Field | Source / type | JSON-safety treatment | Status |
|---|---|---|---|
| `period` | Route input, declared `period: str` throughout (never reparsed into another type) | None needed — single variable, string end-to-end, no parallel typed version exists | OK — no transformation, no ambiguity |
| `anchor_date` | Route input, `str` | Explicitly declared (16_design_corrections.md) to be the original unparsed request string, never `anchor_date_parsed` (the `date` object used only for `resolve_report_period`) | OK — explicitly stated, fixed this round |
| `period_start` | `resolve_report_period` output, typed `date` | `.isoformat()` explicitly declared (14_design_corrections.md) | OK — explicitly stated |
| `period_end` | `resolve_report_period` output, typed `date` | `.isoformat()` explicitly declared (14_design_corrections.md) | OK — explicitly stated |
| `dates` | `resolve_report_period` output, declared `list[str]` (step 10) | None needed — already string-typed at the source, no parallel date-object version is ever constructed or referenced | OK — no transformation, no ambiguity |
| `confirmed_days` | "count of distinct dates ... with status='confirmed'" (step 11) | None needed — a plain count, always `int`, natively JSON-safe | OK |
| `elapsed_days` | "count of dates in `dates` <= min(period_end, today_berlin)" (step 11) | None needed — a plain count, always `int`, natively JSON-safe | OK (see Recommended Improvements for a non-blocking computation-method clarity note) |

No field in the dict retains an undeclared raw `date`/`datetime` value, and no field has two differently-typed candidate variables (the `anchor_date` vs. `anchor_date_parsed` ambiguity that caused the prior two rounds' findings) left unresolved.

## Recommended Improvements
1. **`elapsed_days` computation method is described at the semantic level only, not operationally**
   - Location: `10_architecture.json` §`internal_flow` step 11 (`compute_report`): "elapsed_days = count of dates in `dates` <= min(period_end, today_berlin) inclusive"
   - Improvement: State explicitly that `elapsed_days` should be computed via date arithmetic (`(min(period_end, today_berlin) - period_start).days + 1`) rather than by iterating `dates` (a `list[str]`) and comparing each string element directly against the `date` object `min(period_end, today_berlin)` — Python does not support `<=` between `str` and `datetime.date` and would raise `TypeError` if implemented that literally.
   - Why: This is a lower-confidence ambiguity than the three resolved `period_summary` findings — unlike those, no single literal reading of the current text is clearly the only implementation path, and the natural implementation (date arithmetic on the `date`-typed threshold) avoids the mismatch entirely. Not blocking, but worth closing explicitly given this sprint's history with type-mismatch gaps in this exact function.
2. **Orphaned `habit_results` on an archived habit during a Draft day (carried from `11_design_review.md` / `13_design_review.md` / `15_design_review.md`)**
   - Location: `00_draft.md` §Defaults and Merging; `10_architecture.json` §`contracts.invariants` (Checked-value rule); §`internal_flow` step 7 (Draft branch)
   - Improvement: Still unaddressed. A Draft day's displayed habit list is always `resolve_active_habits_for_date` (current active window), never "habits with an existing saved row ∪ current active window" — so a habit archived after a checkbox was draft-saved for it silently disappears from the Daily Review screen and from the next PUT's expected set, orphaning its `habit_results` row. Document this as an explicit non-goal, or extend the Draft-branch habit list to the union of active-window habits and habits with an existing saved row for that date.
   - Why: Preserved purely for traceability — correctly scoped as non-blocking across three prior review rounds (rare in a single-user app); not required for approval.

## Scaffold-Only Observations
1. **No `ColumnSchema` module constants scaffolded (carried from `11_design_review.md` / `13_design_review.md` / `15_design_review.md`)**
   - Location: `10_scaffolding.json` `backend/routers/habits.py`, `reviews.py`, `reports.py` `public_objects`
   - Observation: Still absent. Unlike EssayCards' `REVIEW_STATS_SUMMARY_SCHEMA`/`ACTIVITY_SCHEMA` module-level constants, no `HABIT_SCHEMA`/equivalent is scaffolded for any of the three Dataset-returning routers. Row shapes are fully specified in prose (`exposed_surfaces.row_shape`).
   - Impact on implementation: None blocking; adding the constants would keep the stub closer to the module structure the implementer will actually produce.

## Hard Rule Violations
None identified. `R-CON-AL-03` (Invariant Realizability) and `R-CON-BP-10` (Input Sufficiency), both violated in `15_design_review.md` by the undeclared `anchor_date` conversion/serialization, are now satisfied: the str→date pre-step is named (`_parse_date_param` in `backend/routers/reports.py`, a declared file-local duplicate of `reviews.py`'s helper, consistent with R-CON-BP-10's note that the dependency must be declared via a defined pre-step), and `anchor_date`'s JSON-safety is explicitly resolved (original string, never the parsed value).

## Open Uncertainties
1. **Long-term status of the Dataset-plus-sibling-field pattern (carried from `11_design_review.md` / `13_design_review.md` / `15_design_review.md`)**
   - Location: `10_architecture.json` §`open_questions[0]`; §`risks` (period_summary risk entry)
   - Uncertainty: Whether `GET /reports` returning `Dataset` plus an additive `period_summary` top-level field is an acceptable pattern long-term, or should be promoted into a versioned platform Dataset extension (R-CON-BP-04 §11).
   - Why it matters: This pattern took three correction rounds to make byte-correct by hand (sibling-field dict merge bypassing pydantic's `mode="json"` serializer twice surfaced raw-type defects). That cost is evidence relevant to the long-term question, not just a one-off implementation detail.
   - Suggested owner: Architecture
2. **Future exposure of the reserved `source` column (carried from `11_design_review.md` / `13_design_review.md` / `15_design_review.md`)**
   - Location: `10_architecture.json` §`open_questions[1]`
   - Uncertainty: Whether a later sprint adding an automatic result source will need `GET /reviews/{date}` to surface `source` and whether the UI will need a manual-vs-automatic visual distinction.
   - Why it matters: Affects whether this sprint's row shape needs a reserved-but-unexposed field path later, vs. an additive change.
   - Suggested owner: Product

## Minimal Change Set
None identified. No change is required before implementation may proceed.

## Approval Condition
None — approved as-is. All three correction rounds (`12`, `14`, `16`) resolved their respective Approval Conditions, this round's full-field audit of `period_summary` found no remaining or new gap, and no other dimension (layer correctness, contract completeness, persistence consistency, security/exposure, UI test coverage) regressed from the state verified in `11_design_review.md`.
