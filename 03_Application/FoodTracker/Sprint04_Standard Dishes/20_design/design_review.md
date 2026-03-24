# Design Review — food_tracker (Sprint 04: Standard Dishes)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design is architecturally sound and the domain model is correctly classified at `03_Application`. Contracts are well-specified, invariants are precise, and the flag-on-row approach is consistently applied. Two issues must be resolved before handoff to the implementer: the migration file path is inconsistent across the design artifacts, and the `row_actions` declared on `GET /api/food/entries` includes `'copy'` while the Sprint 04 UI removes the Copy menu item without resolving its status. These are discrete, targeted fixes. No redesign is required.

---

## Confirmed Problems

1. **Migration file path is inconsistent across artifacts**
   - Severity: Critical
   - Location: `component_architecture.json → persistence.schema_artifact` vs. `component_architecture.json → persistence.sprint04_note` and `component_architecture.json → deferrals.application_implementer[0]` and `component_scaffold.json → files[0].path`
   - Why it is a problem: `persistence.schema_artifact` declares the migration file as `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/migration_004.sql`. Every other reference in both artifacts — the `sprint04_note`, the implementer deferral, and the scaffold file path — names it `migrations/003_add_standard_fields.sql` under the FoodTracker root. The `migration_004.sql` file does not exist. An implementer following `persistence.schema_artifact` will look for a non-existent file and either create a wrongly-placed migration or fail to locate the authoritative DDL specification.
   - Impact: The migration may be incorrectly placed, misnamed, or skipped entirely, breaking schema consistency with the implementation.
   - Likely Cause (Design Phase): Ambiguous Definition — `schema_artifact` appears to have been written assuming a design-folder SQL file, while all execution-oriented references were updated to use the migrations directory convention without back-propagating to `persistence.schema_artifact`.

2. **`row_actions` includes `'copy'` but the Sprint 04 UI removes the Copy menu item without product resolution**
   - Severity: Major
   - Location: `component_scaffold.json → files[1] (entries.py) → public_objects[1] (list_entries) → methods[0].purpose` ("Row_actions remain ['delete', 'copy', 'edit']") and `component_architecture.json → open_questions[0]`
   - Why it is a problem: The UI_Data_Contract rule (`00_Blueprint/UI/01_UI_Contract`) states that `row_actions` is declared by the backend and the frontend renders only what the backend declares. Sprint 03 established `row_actions = ['delete', 'copy', 'detail']`. Sprint 04 replaces flat row buttons with a ThreeDotsMenu containing only Standard/Remove Standard/Delete — no Copy action. The `list_entries` purpose in the scaffold still declares `row_actions` as `['delete', 'copy', 'edit']`. The open question assigns this to "product" but the design proceeds with implementation instructions that silently drop Copy from the UI while keeping it in `row_actions`. This is not a safe deferral: if an implementer follows the scaffold's `list_entries` declaration and the UI_Data_Contract literally, a frontend must render a Copy action that no menu item supports.
   - Impact: The implementer receives two contradictory instructions. Either Copy stays in `row_actions` and the UI silently violates the contract by not rendering it, or Copy is removed and the scaffold must be corrected. The current state requires the implementer to make a product decision that is explicitly flagged as unresolved.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the open question was surfaced but not discharged before producing the scaffold, leaving a contract split between the declared `row_actions` and the specified UI component behavior.

---

## Recommended Improvements

1. **Resolve the migration path to a single canonical reference**
   - Location: `component_architecture.json → persistence.schema_artifact`
   - Improvement: Change `persistence.schema_artifact` to `03_Application/FoodTracker/migrations/003_add_standard_fields.sql` to match every other reference. Remove the reference to `migration_004.sql` entirely or document explicitly that no SQL file lives under `20_design/`.
   - Why: Implementers and reviewers look at `persistence.schema_artifact` as the authoritative path to the migration DDL. A single canonical path eliminates the ambiguity.

2. **Discharge the Copy action question before scaffold handoff**
   - Location: `component_architecture.json → open_questions[0]` and `component_scaffold.json → files[1] → public_objects[1].purpose`
   - Improvement: Product must confirm one of two paths: (a) Copy is retained as a separate flat action outside the ThreeDotsMenu — in which case the scaffold must describe where it renders and `row_actions` retains `'copy'`; or (b) Copy is removed from this page in Sprint 04 — in which case `row_actions` must be updated to remove `'copy'` from `list_entries` and the `copy_entry` endpoint remains available but is not surfaced on the Entries page. The design note (arch `open_questions[0]`) already correctly identifies the question and owner; it must be answered before the scaffold is handed to the implementer.
   - Why: The UI_Data_Contract binds frontend rendering to backend-declared `row_actions`. A mismatch breaks the contract and creates undefined frontend behavior.

3. **Correct the invalid SQL fragment in `internal_flow` step 2**
   - Location: `component_architecture.json → internal_flow[1] (fetch_standards_page) → description`
   - Improvement: Remove `ORDER BY SUM(logged_at) DESC` from the description. The phrase appears mid-sentence before the correct alternative (`MAX(logged_at) DESC`) but will mislead an implementer scanning the query skeleton. The scaffold already uses `MAX(logged_at) DESC` correctly.
   - Why: `SUM(logged_at)` is not valid SQL. An implementer who transcribes the `internal_flow` description verbatim will receive a database error.

---

## Scaffold-Only Observations

1. **`StandardsPagePayload`, `StandardDish`, and `TodayInstance` types are private to `StandardsPage.tsx`**
   - Location: `component_scaffold.json → files[5] (StandardsPage.tsx) → private_objects`
   - Observation: All three contract types for the `GET /api/food/standards` response are scoped private to `StandardsPage.tsx`. If a future sprint adds a second consumer of `StandardsPagePayload` (e.g. a widget or a summary component), these types will need to be promoted. The current sprint scope does not require this, so private placement is appropriate, but the convention diverges from how `Dataset` types are handled (imported from platform).
   - Impact on implementation: No impact in this sprint. Note for future: if `StandardsPagePayload` is consumed elsewhere, it should be promoted to a shared contract file rather than duplicated.

2. **`_serialise_standard_log_result` duplicates `_serialise_entry_detail` output shape**
   - Location: `component_scaffold.json → files[1] (standards.py) → private_objects[0]`
   - Observation: The scaffold correctly prohibits `standards.py` from importing `_serialise_entry_detail` from `entries.py`, requiring a parallel private serialiser. The risk of divergence on future EntryDetail field additions is acknowledged in `component_architecture.json → risks[4]`. The scaffold is consistent with its own rule but the parallel implementation is a known maintenance liability.
   - Impact on implementation: The implementer must manually keep both serialisers in sync when EntryDetail is extended in future sprints. A reviewer checklist item should confirm field parity between the two serialisers at the time of review.

---

## Hard Rule Violations

1. **UI_Data_Contract — `row_actions` declared by producer not honoured by consumer**
   - Rule Source: `00_Blueprint/UI/01_UI_Contract` — "row_actions is declared by backend, not hardcoded in frontend. Frontend renders only what backend declares."
   - Location: `component_scaffold.json → files[1] (entries.py) → public_objects[1] (list_entries).purpose` declares `row_actions=['delete', 'copy', 'edit']`; `component_scaffold.json → files[4] (EntriesPage.tsx) → private_objects[1] (ThreeDotsMenu)` renders only Standard/Remove Standard/Delete.
   - Violation: The backend declares `'copy'` and `'edit'` as row actions; the frontend component renders neither. The contract rule requires the frontend to render every declared action. The current design creates an undischarged divergence.
   - Required Fix: Either remove `'copy'` and `'edit'` from `row_actions` in `list_entries` to match what the frontend renders, or add Copy and Edit items to the ThreeDotsMenu specification. Product must resolve which path applies before implementation begins (see Confirmed Problem 2).

---

## Open Uncertainties

1. **Whether `'edit'` is a valid Sprint 04 row action**
   - Location: `component_scaffold.json → files[1] (entries.py) → public_objects[1] (list_entries).purpose`
   - Uncertainty: Sprint 03 declared `row_actions = ['delete', 'copy', 'detail']` (architecture.json line 157). Sprint 04 scaffold changes this to `['delete', 'copy', 'edit']` — `'detail'` is removed and `'edit'` is added. This change is not described anywhere in the Sprint 04 draft or architecture. It is unclear whether this is an intentional Sprint 04 change, a typo, or a carry-over of an earlier draft value.
   - Why it matters: If `'detail'` is silently dropped, the detail view link that Sprint 03 implemented becomes unreachable via the row actions contract. If `'edit'` is added, a frontend renderer must handle it.
   - Suggested owner: Implementer (verify against Sprint 03 implementation and confirm whether `'detail'` is retained or intentionally dropped).

2. **`DELETE /api/food/entries/{id}` can silently delete a standard row from the Entries page**
   - Location: `component_architecture.json → risks[2]`
   - Uncertainty: The design acknowledges dangling `source_standard_id` references when a standard row is deleted. It does not define whether the Entries page should warn the user that deleting a standard will affect the Standards page (e.g., today's aggregated instances will lose their standard reference). The current design makes deletion silent.
   - Why it matters: A user who deletes a standard from Entries may see the Standards bottom section shrink unexpectedly while today's top section may show orphaned aggregated rows.
   - Suggested owner: Product (decide whether a deletion warning is required when `row.standard === true`; acceptable to defer to a later sprint but the decision point should be recorded).

---

## Minimal Change Set

1. Update `component_architecture.json → persistence.schema_artifact` from `03_Application/FoodTracker/Sprint04_Standard Dishes/20_design/migration_004.sql` to `03_Application/FoodTracker/migrations/003_add_standard_fields.sql` to match all other references.
2. Obtain product confirmation on the Copy action fate (retain as flat button outside ThreeDotsMenu, or remove from Entries page in Sprint 04), then update `component_scaffold.json → files[1] (entries.py) → list_entries.purpose → row_actions` and the ThreeDotsMenu specification to be consistent.
3. Remove the invalid `ORDER BY SUM(logged_at) DESC` clause fragment from `component_architecture.json → internal_flow[1] (fetch_standards_page) → description`, retaining only `MAX(logged_at) DESC`.

---

## Approval Condition

`persistence.schema_artifact` resolves to a single consistent path, and `row_actions` in `list_entries` matches the set of actions rendered by the Sprint 04 ThreeDotsMenu specification.
