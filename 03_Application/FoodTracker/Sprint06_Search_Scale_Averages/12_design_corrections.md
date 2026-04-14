# Design Corrections — FoodTracker

## Applied Changes

1. **Added `10_schema.sql`**
   - Review Source: `11_design_review.md §Minimal Change Set item 1`, `§Hard Rule Violations item 1`
   - Files Updated: `03_Application/FoodTracker/Sprint06_Search_Scale_Averages/10_schema.sql` (new)
   - Change: Created the sprint-local schema snapshot containing the complete `foodtracker.food_logs` DDL from the current `schema.sql`, extended with the new `quantity_g NUMERIC(7,1) DEFAULT NULL` column and `CONSTRAINT food_logs_quantity_g_pos CHECK (quantity_g IS NULL OR quantity_g > 0)`. This matches the migration declared in `10_architecture.json §internal_flow[step 5]` and `00_draft.md §4.1`.

2. **Added `10_test_spec.md`**
   - Review Source: `11_design_review.md §Minimal Change Set item 2`, `§Hard Rule Violations item 2`
   - Files Updated: `03_Application/FoodTracker/Sprint06_Search_Scale_Averages/10_test_spec.md` (new)
   - Change: Created the test spec covering all four feature areas (quantity_g intake scaling, entry detail/edit/copy, report alcohol column, avg scope extension) with 12 backend scenarios and 8 UI scenarios. UI scenarios for the alcohol view selector and chart are marked `[UI]` (automatable against the shell). Scenarios for week avg line, entry search, and EntryDetail rescale UX are marked `[UI — manual]` as execution infrastructure for the detail page rescale requires sprint-local judgment.

3. **Updated `EntryDetail` named contract in `ARCHITECTURE_EXCEPTIONS.md`**
   - Review Source: `11_design_review.md §Minimal Change Set item 3`, `§Hard Rule Violations item 3`
   - Files Updated: `03_Application/FoodTracker/ARCHITECTURE_EXCEPTIONS.md §EXC-FT-03`
   - Change: Added `quantity_g` to the `EntryDetail` field list in EXC-FT-03. Field type: `float | null`. EXC-FT-04 references EXC-FT-03 by name and therefore inherits the updated definition automatically — no separate edit needed for EXC-FT-04.

## Unchanged by Design

All sections of `10_architecture.json` and `10_scaffolding.json` were preserved verbatim. The review found no issues in these artifacts — the three corrections produced new files or updated an external contract document. No design decisions were altered.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — `10_schema.sql`, `10_test_spec.md`, and an updated `EntryDetail` contract are all now present and consistent with the design.
- Notes: None.
