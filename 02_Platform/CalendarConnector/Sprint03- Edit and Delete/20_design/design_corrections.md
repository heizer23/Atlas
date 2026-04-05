# Design Corrections — calendar_connector (Sprint03: Edit and Delete)

## Applied Changes

1. **Resolve POST HTTP status code for idempotent return**
   - Review Source: `design_review.md` § Minimal Change Set item 1; Confirmed Problem 1
   - Files Updated: `20_design/architecture.json`
   - Change: In `interfaces.provides`, replaced the ambiguous `200/201` notation on the POST entry with the definitive conditional mapping: `201` on `status='created'`, `200` on `status='existing'`. In `open_questions[0]`, added `"resolved": true` and a `"resolution"` field documenting the RFC 9110 rationale. The question object is retained for traceability.

2. **Add `atlas_event_id` parameter to `write_decision_log` interface**
   - Review Source: `design_review.md` § Minimal Change Set item 2; Confirmed Problem 2
   - Files Updated: `20_design/architecture.json`, `20_design/scaffolding.json`
   - Change: In `architecture.json` `interfaces.consumes`, extended the `write_decision_log` signature with `atlas_event_id=None` as a trailing keyword argument. In `scaffolding.json` `token_store.py` `write_decision_log`, added `atlas_event_id: Optional[str] = None` to the `args` list and rewrote the `purpose` field to document the new parameter, its default behavior, and the backing migration.

3. **Add migration to extend `calendar_decision_log` with `atlas_event_id` column**
   - Review Source: `design_review.md` § Minimal Change Set item 2
   - Files Updated: `02_Platform/CalendarConnector/migrations/004_decision_log_atlas_event_id.sql` (new file); `20_design/architecture.json` `persistence` block; `20_design/architecture.json` `deferrals.platform_implementer`
   - Change: Created `004_decision_log_atlas_event_id.sql` with `ALTER TABLE calendar_decision_log ADD COLUMN IF NOT EXISTS atlas_event_id TEXT`. Column is nullable for backward compatibility with Sprint02 create entries. Added `schema_artifact_addendum` reference in `persistence` block. Added a deferral item instructing the implementer to run the migration.

4. **Add call-site obligation note to `_get_valid_access_token`**
   - Review Source: `design_review.md` § Minimal Change Set item 3
   - Files Updated: `20_design/scaffolding.json`
   - Change: Replaced the `purpose` field of `_get_valid_access_token` in `calendar.py` private objects with text that explicitly states the `isinstance(result, JSONResponse)` branch obligation at every call site, and names the three handlers that use the helper.

## Unchanged by Design

All sections of `architecture.json` and `scaffolding.json` not identified in the Minimal Change Set were preserved verbatim. The `003_event_index.sql` migration was not modified. Existing `interfaces.provides` entries for PATCH and DELETE, all `internal_flow` steps, `contracts`, `dependencies`, `shared_views`, `risks`, `deferred_decisions`, and all `scaffolding.json` objects outside `write_decision_log` and `_get_valid_access_token` are unchanged.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: The review's Minimal Change Set item 2 stated "a Sprint03 migration ALTER TABLE or a note in the implementation deferral list is sufficient." A new migration file (`004_`) was chosen over an implementation note because the column must exist at runtime and a migration file is the correct durable artifact for schema changes in this codebase (consistent with prior migrations). The deferral list was also updated to direct the implementer to run it. No scope was added beyond what the review required.
