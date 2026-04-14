# Design Corrections — FoodTracker

## Applied Changes
1. **Add ARCHITECTURE_EXCEPTIONS.md update to application_implementer deferrals**
   - Review Source: `11_design_review.md` — Minimal Change Set item 1
   - Files Updated: `10_architecture.json`
   - Change: Added deferral item: "Update ARCHITECTURE_EXCEPTIONS.md EXC-FT-03: in the EntryDetail named contract field list, replace 'quantity_g: float | null' with 'base_quantity: number'; update EXC-FT-04 reference accordingly"

2. **Clarify fixtures.sql NULL replacement in test_writer deferrals**
   - Review Source: `11_design_review.md` — Minimal Change Set item 2
   - Files Updated: `10_architecture.json`
   - Change: Updated test_writer deferral from "Extend tests/fixtures.sql to include base_quantity values; remove quantity_g references" to "Update tests/fixtures.sql: rename quantity_g column to base_quantity in all INSERT statements; replace all NULL values with 100 (base_quantity is NOT NULL DEFAULT 100 after migration)"

## Unchanged by Design
- All sections of `10_architecture.json` other than `deferrals.application_implementer` and `deferrals.test_writer` were preserved verbatim.
- `10_scaffolding.json`, `10_schema.sql`, and `10_test_spec.md` are unchanged.

## Review Alignment Check
- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — `10_architecture.json` deferrals now include an explicit instruction to update `ARCHITECTURE_EXCEPTIONS.md` EXC-FT-03 with the renamed field and updated type.
- Notes: None.
