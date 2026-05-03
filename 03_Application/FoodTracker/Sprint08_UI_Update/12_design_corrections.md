# Design Corrections — FoodTracker Sprint08_UI_Update

**Date:** 2026-05-03
**In response to:** 11_design_review.md (APPROVED_WITH_CHANGES)

## Corrections Applied

### Issue 1 — internal_flow step 3 contradictory dual-approach description

**Finding:** Step 3 (json_logging_date_context) described two mutually exclusive implementation options inline and then chose one without cleanly removing the other.

**Fix applied:** Rewrote step 3 to state exactly one behavior:
- The date picker updates the displayed template string so the user sees the correct date when copying
- No client-side JSON manipulation at submit time
- The backend takes the timestamp field from the user-pasted JSON exactly as provided
- The deferral for ShellEntry.tsx was updated to match this single approach

### Issue 2 — schema_artifact incorrect reference

**Finding:** `persistence.schema_artifact` was set to `"10_schema.sql"` but no schema file exists or is produced this sprint.

**Fix applied:**
- Set `persistence.owns_persistent_state` to `false`
- Set `persistence.schema_artifact` to `null`
- Added a `note` field: "No schema changes this sprint. Schema is unchanged from Sprint07_Base_Quantity."

## Artifacts Modified

- `10_architecture.json` — internal_flow step 3 rewritten; persistence block corrected
