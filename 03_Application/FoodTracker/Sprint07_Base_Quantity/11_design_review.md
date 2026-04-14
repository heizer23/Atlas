# Design Review — FoodTracker

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The Sprint 07 design is a clean, minimal rename sprint. All migration steps, backend renames, and frontend changes are correctly specified. One blocking gap: `ARCHITECTURE_EXCEPTIONS.md` defines the `EntryDetail` named contract with `quantity_g: float | null` and this definition is not updated to `base_quantity: number`. After implementation the named contract in the exception file will be stale and will conflict with the actual endpoint shape. The test fixture update is correctly deferred but must explicitly call out that `NULL` values are no longer valid for `base_quantity`.

## Confirmed Problems
1. **EntryDetail named contract not updated in ARCHITECTURE_EXCEPTIONS.md**
   - Severity: Major
   - Location: `03_Application/FoodTracker/ARCHITECTURE_EXCEPTIONS.md` — EXC-FT-03 and EXC-FT-04, `EntryDetail` contract definition
   - Why it is a problem: EXC-FT-03 defines `EntryDetail` as including `quantity_g: float | null`. After this sprint the field is `base_quantity: number` (non-null). The exception file is the authoritative named contract referenced by ARCHITECTURE_EXCEPTIONS.md for EXC-FT-04 and EXC-FT-03. No artifact in the sprint instructs the implementer to update it.
   - Impact: The authoritative named contract will diverge from the actual endpoint shape. Future reviewers and implementers relying on the exception file will use the wrong field name and type.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the rename was propagated through code artifacts but not through the contract-registration artifact that independently documents the same field.

2. **fixtures.sql must not contain NULL for base_quantity, but the deferrals do not state this explicitly**
   - Severity: Minor
   - Location: `10_architecture.json` — `deferrals.test_writer`; `03_Application/FoodTracker/tests/fixtures.sql`
   - Why it is a problem: The existing `fixtures.sql` uses `quantity_g` column name and inserts two NULL values. After migration, `base_quantity` is `NOT NULL`. If the implementer updates the column name but forgets to replace the NULLs with 100, fixture loading will fail with a NOT NULL constraint violation. The deferral text says "remove quantity_g references" but does not state "replace NULL values with 100".
   - Impact: Test fixture loading fails; test suite cannot run until the implementer diagnoses the constraint violation.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the semantic change from nullable to NOT NULL was not propagated into the fixture update instruction.

## Recommended Improvements
1. **Add explicit fixture NULL-replacement instruction to deferrals**
   - Location: `10_architecture.json` — `deferrals.test_writer`
   - Improvement: Change "Extend tests/fixtures.sql to include base_quantity values; remove quantity_g references" to "Update tests/fixtures.sql: rename quantity_g column to base_quantity in all INSERT statements; replace all NULL values with 100 (base_quantity is NOT NULL after migration)."
   - Why: Prevents implementer confusion over why fixture loading fails after the column rename.

## Scaffold-Only Observations
None identified.

## Hard Rule Violations
None identified.

## Open Uncertainties
None identified.

## Minimal Change Set
1. Add a deferral item to `10_architecture.json` instructing the implementer to update `ARCHITECTURE_EXCEPTIONS.md` EXC-FT-03: change `quantity_g: float | null` to `base_quantity: number` in the `EntryDetail` named contract definition.
2. Update the test_writer deferral to explicitly state that NULL values in fixtures.sql must be replaced with 100.

## Approval Condition
- `10_architecture.json` deferrals include an explicit instruction to update `ARCHITECTURE_EXCEPTIONS.md` EXC-FT-03 with the renamed field and updated type.
