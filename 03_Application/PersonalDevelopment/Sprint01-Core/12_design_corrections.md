# Design Corrections — personal_development

## Applied Changes

1. **Set `persistence.owns_persistent_state` to `false`**
   - Review Source: `11_design_review.md §Minimal Change Set [1]`, `§Hard Rule Violations [1]` (R-CON-BP-09)
   - Files Updated: `10_architecture.json`
   - Change: `owns_persistent_state` changed from `true` to `false`. Field `schema_artifact` renamed to `migration_artifact` to clarify this is a migration targeting TaskTracker-owned tables, not a self-owned schema. `ownership` updated from `"private_application_state"` to `"none — all persistence owned by TaskTracker"`. Prose in `notes` was retained verbatim.

2. **Declare TRAINING_UNIT_SCHEMA ColumnSchema columns explicitly**
   - Review Source: `11_design_review.md §Minimal Change Set [2]`, `§Confirmed Problems [2]` (R-CON-AL-01)
   - Files Updated: `10_architecture.json`
   - Change: The last item of `deferrals.application_implementer` was replaced with a concrete column enumeration: `id` (string), `title` (string), `status` (enum: open/in_progress/pending/done), `priority` (enum: low/medium/high), `labels` (string, nullable), `actual_duration_minutes` (number, nullable), `completed_at` (date, nullable), `last_child_completed_at` (date, nullable), `completed_child_count` (number), `total_child_count` (number), `description` (string, nullable, detail_visible: true). Columns match the `TrainingUnitRow` interface declared in `10_scaffolding.json §types.ts`.

3. **Declare child-task fetch endpoint in `contracts.consumes`**
   - Review Source: `11_design_review.md §Minimal Change Set [3]`, `§Confirmed Problems [3]`, `§Hard Rule Violations [2]` (R-CON-AL-01)
   - Files Updated: `10_architecture.json`
   - Change: Added `TaskTracker GET /api/tasks?task_type=training_session&parent_task_id=<uuid>` to `contracts.consumes` immediately after the existing `GET /api/tasks` entry, with full specification: parameters (`task_type=training_session` fixed, `parent_task_id` uuid required), ordering (`created_at ASC`), empty-result behavior (return empty rows array), and time basis (server). Removed the corresponding open question from `deferred_decisions` (was index 1).

4. **Remove PreferenceStore contradiction from `deferred_decisions`**
   - Review Source: `11_design_review.md §Confirmed Problems [4]` (R-CON-BP-09, Minor — reconcile non-blocking inconsistency)
   - Files Updated: `10_architecture.json`
   - Change: Removed `deferred_decisions[0]` ("Whether PreferenceStore should be used…") because `deferrals.ui_implementer[2]` already specifies `PreferenceStore scope=learning.unit-list`. The contradicting open-ended deferral was eliminated; the concrete specification in `ui_implementer` was left intact. After this removal, `deferred_decisions` retains one remaining entry (label filtering server-side vs. client-side).

## Unchanged by Design

All sections not listed above — `classification`, `contracts.provides`, `contracts.invariants`, `contracts.failure_modes`, `shared_views`, `interfaces`, `internal_flow`, `dependencies`, `deferrals.ui_implementer`, `deferrals.test_writer`, `deferrals.reviewer`, `risks`, `open_questions`, and all of `10_scaffolding.json` — were preserved verbatim.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes
- Notes: The non-blocking inconsistency (item 4 above) was also resolved per the user instruction. The `open_questions` array retains the child-task fetch question entry (originally at index 1) — this is a prose-level duplicate of the now-removed `deferred_decisions` entry. It was left in place as `open_questions` is not part of the Minimal Change Set and the review did not require its removal; however, a human reviewer may wish to remove it for cleanliness in a subsequent pass.
