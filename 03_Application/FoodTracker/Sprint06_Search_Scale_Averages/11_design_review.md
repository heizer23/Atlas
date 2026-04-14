# Design Review — FoodTracker

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The Sprint 06 design is coherent, well-scoped, and correctly layer-classified. All behavioral logic is explicitly specified and implementable. Two required artifacts are absent: `10_schema.sql` (mandated because `persistence.owns_persistent_state == true`) and `10_test_spec.md` (mandated because `.tsx` files appear in the scaffolding). Both must be added before implementation proceeds. Additionally, the existing `EntryDetail` contract in `ARCHITECTURE_EXCEPTIONS.md` must be updated to include `quantity_g`, since the design extends this named contract.

## Confirmed Problems

1. **Missing `10_schema.sql`**
   - Severity: Major
   - Location: `03_Application/FoodTracker/Sprint06_Search_Scale_Averages/` (absent file); `10_architecture.json §persistence`
   - Why it is a problem: `persistence.owns_persistent_state == true` and `schema_artifact: "10_schema.sql"` are declared in `10_architecture.json`, but no `10_schema.sql` exists in the sprint folder. R-PRO-BP-01 §1 and the reviewer Step 1 checklist both require this artifact when the component owns persistent state.
   - Impact: Reviewers and implementers cannot verify the schema change is correct. The migration `migrations/005_add_quantity_g.sql` adds a column, but there is no sprint-local snapshot of the complete target schema state.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the sprint designer declared persistence ownership in the architecture but did not produce the corresponding schema snapshot artifact.

2. **Missing `10_test_spec.md`**
   - Severity: Major
   - Location: `03_Application/FoodTracker/Sprint06_Search_Scale_Averages/` (absent file); `10_scaffolding.json §files` (`.tsx` files listed)
   - Why it is a problem: `10_scaffolding.json` lists `ReportPage.tsx`, `EntriesPage.tsx`, and `EntryDetailPage.tsx` as changed files. R-PRO-BP-01 §10 requires `10_test_spec.md` with at least one `[UI]` scenario when `.tsx` files are in scope. The reviewer instructions (Step 2, item 10) confirm this is a blocking Major finding.
   - Impact: There are no defined acceptance criteria for any of the four feature areas. The test runner cannot execute and the sprint cannot proceed to `TESTS_PASSING` state. The implementer has no behavioral targets for the backend changes either.
   - Likely Cause (Design Phase): Missing Rule Enforcement — the designer produced architecture and scaffolding but did not follow through to the test spec artifact required by the sprint process contract.

3. **`EntryDetail` named contract not updated in `ARCHITECTURE_EXCEPTIONS.md`**
   - Severity: Major
   - Location: `10_architecture.json §interfaces.exposed_surfaces` (GET /api/food/entries/:id, POST /api/food/entries/:id/copy); `03_Application/FoodTracker/ARCHITECTURE_EXCEPTIONS.md §EXC-FT-03, EXC-FT-04`
   - Why it is a problem: The sprint adds `quantity_g: float | null` to `EntryDetail`. EXC-FT-04 and EXC-FT-03 define `EntryDetail` with a fixed field list that does not include `quantity_g`. The architecture references "registered exception" for both affected endpoints, but the exception definition is stale. R-CON-BP-09 (Cross-Artifact Truth Consistency) requires that all artifacts reflect the same resolved decision.
   - Impact: The implementer has no formally registered field list for the updated `EntryDetail`. The exception file will disagree with the implemented contract, misleading future reviewers and agents.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the sprint addressed backend serialisation (step 6 in `internal_flow`) but did not propagate the contract update to the exception registry.

## Recommended Improvements

1. **Cross-field check placement note in test spec**
   - Location: `10_architecture.json §internal_flow[step 4]`
   - Improvement: The test spec (once written) should include a scenario that verifies cross-field checks (`good_fat_g <= fat_g`, `red_meat_g <= meat_g`) apply to the per-100g values, not to the scaled stored values.
   - Why: The design correctly states checks apply before scaling, but this is a non-obvious invariant that is easy to implement incorrectly. A scenario makes it a traceable acceptance criterion.

2. **`NULL` treatment for `quantity_g` in existing rows**
   - Location: `10_architecture.json §risks[1]`
   - Improvement: The test spec should include a scenario confirming that a row with `quantity_g = NULL` (legacy row) loads correctly in `EntryDetailPage` — specifically that the rescale UX is hidden and the flat edit form is shown.
   - Why: The design states the rescale UX is "opt-in (only shown when `quantity_g` is non-null)" — this boundary condition is critical and easily missed in implementation.

## Scaffold-Only Observations

1. **`YearComboPanel` rename deferred**
   - Location: `10_scaffolding.json §files[ReportPage.tsx]`; `10_architecture.json §internal_flow[step 10]`
   - Observation: The design defers the rename of `YearComboPanel` → `AvgComboPanel` as optional ("or leave the name unchanged"). This is fine functionally but leaves an inconsistency between the component name and its new scope.
   - Impact on implementation: No functional impact. Implementer should pick one name and use it consistently; the scaffolding entry for `ReportPage.tsx` should reflect whichever name is chosen.

## Hard Rule Violations

1. **R-PRO-BP-01 §1 — Schema artifact required when component owns persistent state**
   - Rule Source: `.claude/rules/R-PRO-BP.md §1`
   - Location: `03_Application/FoodTracker/Sprint06_Search_Scale_Averages/` (absent `10_schema.sql`)
   - Violation: `persistence.owns_persistent_state == true` and `schema_artifact: "10_schema.sql"` declared, but file is absent from the sprint folder.
   - Required Fix: Add `10_schema.sql` to the sprint folder containing the complete target `foodtracker.food_logs` table DDL (existing columns plus `quantity_g`).

2. **R-PRO-BP-01 §10 — Test spec with UI scenario required when `.tsx` files are in scope**
   - Rule Source: `.claude/rules/R-PRO-BP.md §10`
   - Location: `03_Application/FoodTracker/Sprint06_Search_Scale_Averages/` (absent `10_test_spec.md`); `10_scaffolding.json §files` (`.tsx` files present)
   - Violation: No `10_test_spec.md` exists despite three `.tsx` files being listed as changed.
   - Required Fix: Add `10_test_spec.md` covering: (a) at least one `[UI]` or `[UI — manual]` scenario for each changed frontend component; (b) backend API scenarios for the quantity_g intake path, the report alcohol column, the avg scope extension, and the entry detail/copy changes.

3. **R-CON-BP-09 — Cross-artifact truth consistency violated for `EntryDetail` contract**
   - Rule Source: `.claude/rules/R-CON-BP.md §R-CON-BP-09`
   - Location: `03_Application/FoodTracker/ARCHITECTURE_EXCEPTIONS.md §EXC-FT-03, EXC-FT-04`
   - Violation: The `EntryDetail` named contract defined in `EXC-FT-03` and `EXC-FT-04` does not include `quantity_g`, but the design adds `quantity_g: float | null` to the serialised output.
   - Required Fix: Update `ARCHITECTURE_EXCEPTIONS.md §EXC-FT-03` and `EXC-FT-04` to include `quantity_g: float | null` in the `EntryDetail` field list. This is a sprint corrector task (updating an existing design artifact).

## Open Uncertainties

1. **`PUT /api/food/entries/:id` UI contract listed as `Dataset`**
   - Location: `10_architecture.json §interfaces.exposed_surfaces[PUT /api/food/entries/:id]`
   - Uncertainty: The architecture lists `ui_contract: "Dataset (single row on success)"` for this mutation endpoint. The existing code (verified in `entries.py`) returns a Dataset on success. However, this is a mutation endpoint — R-CON-BP-04 permits non-Dataset shapes for mutations that return only confirmation. The design should clarify whether the Dataset return is intentional (for immediate UI refresh) or whether it should be a 200/204 plus a separate fetch.
   - Why it matters: If the frontend relies on the Dataset return to refresh the detail view without a re-fetch, this is a deliberate design decision that should be stated explicitly rather than inherited silently from prior sprint behavior.
   - Suggested owner: Implementer (accept existing behavior; note in implementation that the Dataset return is the FoodTracker convention for edit endpoints).

## Minimal Change Set

1. Add `10_schema.sql` to `03_Application/FoodTracker/Sprint06_Search_Scale_Averages/` — complete `foodtracker.food_logs` DDL including the new `quantity_g` column and `food_logs_quantity_g_pos` CHECK constraint.
2. Add `10_test_spec.md` to `03_Application/FoodTracker/Sprint06_Search_Scale_Averages/` — covering all four feature areas; must include at least one `[UI]` or `[UI — manual]` scenario.
3. Update `03_Application/FoodTracker/ARCHITECTURE_EXCEPTIONS.md §EXC-FT-03` and `§EXC-FT-04` to add `quantity_g: float | null` to the `EntryDetail` field list.

## Approval Condition

All three items in the Minimal Change Set must be present and consistent before implementation proceeds.
