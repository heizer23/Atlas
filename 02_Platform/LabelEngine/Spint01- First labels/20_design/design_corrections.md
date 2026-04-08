# Design Corrections — label_engine

## Applied Changes

1. **Resolved GET /api/groups pagination model**
   - Review Source: `design_review.md` § Minimal Change Set item 1; Confirmed Problem #1
   - Files Updated: `20_design/architecture.json`
   - Change:
     - `shared_views.provides` — `GroupedObjectsResponse` updated to include a `meta` wrapper: `{ total: int, page: int, page_size: int, page_count: int }`. `total` is defined as total matching object count for the given `object_type` (unpaginated); `page_count` is `ceil(total / page_size)`.
     - `internal_flow[6]` (group_assembly) — replaced the open "implementer must choose" language with a concrete description of the paginate-items-before-grouping model: count total, apply page/page_size offset to the flat ordered list, then group, then populate `meta`.
     - `deferred_decisions[0]` — marked RESOLVED with the chosen model and a cross-reference to `internal_flow[6]` and `shared_views`.
     - `deferrals.platform_implementer` — replaced the open "decide and document" instruction with a directive to implement the paginate-items-before-grouping model and populate all `meta` fields.
     - `open_questions[2]` — marked owner as RESOLVED with a cross-reference.

2. **Added object_type casing invariant**
   - Review Source: `design_review.md` § Minimal Change Set item 2; Confirmed Problem #2
   - Files Updated: `20_design/architecture.json`, `20_Data/schema.sql`
   - Change:
     - `contracts.invariants` — added invariant: `object_type` values are case-sensitive and must be lowercase (e.g., `'task'`, not `'Task'`). Callers are responsible for supplying a lowercase value. LabelEngine does not normalize casing on write or read.
     - `20_Data/schema.sql` — updated the `object_type` column comment to state the lowercase requirement. Added `CHECK (object_type = lower(object_type))` constraint as `object_labels_object_type_lowercase` on `labels.object_labels`.

3. **Declared case-insensitive prefix match for GET /api/labels?q=**
   - Review Source: `design_review.md` § Minimal Change Set item 3; Open Uncertainty #2
   - Files Updated: `20_design/architecture.json`
   - Change:
     - `interfaces.exposed_surfaces[0]` (GET /api/labels) — purpose field updated to declare that the match is a case-insensitive prefix match (e.g., `q=out` matches `'Outside'`) using the `ix_labels_name_lower` index already present in `schema.sql`.

## Unchanged by Design

All sections not listed above were preserved verbatim. This includes: `classification`, `contracts.consumes`, `contracts.provides`, `contracts.failure_modes`, all `shared_views` entries other than `GroupedObjectsResponse`, all `interfaces.exposed_surfaces` entries other than GET /api/labels, all `internal_flow` steps other than step 6, all `dependencies`, `persistence`, `deferrals.ui_implementer`, `deferrals.test_writer`, `deferrals.reviewer`, `deferred_decisions[1–3]`, `risks`, `open_questions[0,1,3]`, `_resolved_orchestrator_questions`, and `scaffolding.json` (no changes required by the review).

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — the pagination model for GET /api/groups is declared as a contract decision in `architecture.json` with `GroupedObjectsResponse` updated to reflect the chosen `total` semantics.
- Notes: The review listed the CHECK constraint on `object_type` as optional ("optionally add CHECK constraint"). It has been applied as it directly enforces the declared invariant and eliminates the silent-mismatch risk the review identified. No other optional items were applied.
