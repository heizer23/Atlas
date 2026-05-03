# Design Review — FoodTracker Sprint08_UI_Update

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-05-03
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|
| 1 | `10_architecture.json` §internal_flow step 3 (json_logging_date_context) | R-CON-BP-11 Behavioral Completeness — interface must define behavior for all allowed inputs without contradictory paths | Step 3 describes two mutually exclusive implementation approaches ("inject selectedDate into pastedJson by parsing it" vs. "prepopulate template only") and then chooses one, but the chosen approach is not cleanly stated. The implementer reads both options and a contradictory resolution. Required fix: rewrite step 3 to state exactly one behavior: the date picker updates the displayed template timestamp for copy convenience only; the user is responsible for editing the JSON timestamp before submitting; the backend takes the timestamp as-is. Remove the "inject into pastedJson" option entirely. |
| 2 | `10_architecture.json` §persistence.schema_artifact | R-CON-BP-07 Canonical Artifact Path — no schema artifact exists in Sprint08 folder | The architecture.json carries forward `"schema_artifact": "10_schema.sql"` but this file does not exist in the Sprint08 folder and no schema changes are made. This reference will mislead the implementer into expecting a schema file. Required fix: set `"schema_artifact": null` (or remove the field) and set `"owns_persistent_state": false` for this sprint since no schema changes occur. Alternatively, note explicitly that the schema is inherited and unchanged. |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json` §internal_flow step 5 | The fixed Save button z-index of 100 may conflict with the shell navigation bar or modals. The risk is acknowledged in the risks section — this is acceptable for this sprint. |
| 2 | `10_architecture.json` §contracts.provides | The copy_entry entry correctly notes the new optional body behavior. For clarity the copy endpoint description could note that empty Content-Type or missing body both fall through to the datetime.now() default — implementer should handle both. This is a minor clarity note, not a blocker. |

## Approval Condition

Fix the two blocking issues: (1) remove the contradictory dual-approach description in internal_flow step 3 and state exactly one behavior for the FoodIntake date context, and (2) correct the schema_artifact reference to reflect that no schema file is produced this sprint.
