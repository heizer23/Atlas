# Redesign Summary — food_tracker (Sprint 04: Standard Dishes)

## Applied Changes

1. **Fix `persistence.schema_artifact` path**
   - Review Source: `design_review.md — Confirmed Problem 1 / Minimal Change Set item 1`
   - Files Updated: `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/component_architecture.json`
   - Change: `persistence.schema_artifact` updated from `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/migration_004.sql` to `03_Application/FoodTracker/migrations/003_add_standard_fields.sql`. All references in both artifacts now point to a single consistent migration path.

2. **Discharge Copy question and align `row_actions` with ThreeDotsMenu spec**
   - Review Source: `design_review.md — Confirmed Problem 2 / Hard Rule Violation 1 / Minimal Change Set item 2`
   - Files Updated: `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/component_scaffold.json`, `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/component_architecture.json`
   - Change (scaffold): `list_entries.purpose` `row_actions` changed from `['delete', 'copy', 'edit']` to `['delete']` with an explicit note that Copy is not surfaced on the Entries page in Sprint 04 and the copy endpoint remains available but is not a declared row action.
   - Change (architecture): `open_questions[0]` (the unresolved Copy product question) removed. Resolution basis: sprint definition "Decided Behavior — Entries page" explicitly lists the three-dots menu items as Standard / Remove Standard / Delete with no Copy item. `contracts.invariants` (line 114 in source) already correctly described the three-item menu and was not changed.

3. **Remove invalid `ORDER BY SUM(logged_at) DESC` fragment**
   - Review Source: `design_review.md — Recommended Improvement 3 / Minimal Change Set item 3`
   - Files Updated: `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/component_architecture.json`
   - Change: `internal_flow[1] (fetch_standards_page).description` — replaced `ORDER BY SUM(logged_at) DESC (or MAX(logged_at) DESC for deterministic ordering)` with `ORDER BY MAX(logged_at) DESC`. The invalid SQL fragment and the parenthetical qualifier are both removed; only the correct clause remains.

## Unchanged by Design

All sections of both artifacts not referenced by the Minimal Change Set were preserved verbatim. This includes all contracts, invariants, failure_modes, internal_flow steps 1/3/4/5, all scaffold files other than the `list_entries.purpose` field, all deferrals, risks, dependencies, interfaces, classification, shared_views, and the remaining open question regarding cross-page refresh behavior.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: The review's approval condition is "`persistence.schema_artifact` resolves to a single consistent path, and `row_actions` in `list_entries` matches the set of actions rendered by the Sprint 04 ThreeDotsMenu specification." Both conditions are now met. The `row_actions` value `['delete']` matches the ThreeDotsMenu spec exactly (Standard/Remove Standard/Delete are conditional label variants of the standard-toggle action plus the delete action; neither Copy nor Edit appears). The `copy_entry` endpoint is preserved in the scaffold as an available endpoint but is correctly not declared as a row action for Sprint 04.
