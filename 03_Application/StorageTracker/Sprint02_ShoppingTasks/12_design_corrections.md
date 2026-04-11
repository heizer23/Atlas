# Design Corrections — StorageTracker

## Applied Changes

1. **by_source row shape unified to flat**
   - Review Source: `11_design_review.md` §Blocking Issues #1
   - Files Updated: `10_architecture.json` (contracts.provides, interfaces.exposed_surfaces, internal_flow.step_17), `10_scaffolding.json` (shopping_tasks.py view_by_source purpose)
   - Change: Removed nested `tasks: list` description from exposed_surfaces. All artifacts now consistently describe one flat row per (task, source_tag) combination, with source_tag as an additional column. 'Other' row for tasks with no source tags. Order: source_tags ASC, Other last, then created_at ASC within group.

2. **ShoppingTaskRow source_tags field confirmed present**
   - Review Source: `11_design_review.md` §Blocking Issues #2
   - Files Updated: `10_architecture.json` §shared_views.provides
   - Change: ShoppingTaskRow already included source_tags: list[str] in the original artifact. Added a clarifying note that source_tags is the snapshot from the item at task creation time. No structural change was needed.

## Unchanged by Design
- All Sprint01 item/history endpoints, internal_flow steps 1–11, persistence schema for items and item_history, dependencies, ui views, and scaffolding for items.py, database.py, Dockerfile, compose.yml are preserved verbatim.

## Review Alignment Check
- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — by_source row shape is now flat and consistent across contracts.provides, exposed_surfaces, internal_flow, and scaffolding; ShoppingTaskRow includes source_tags.
- Notes: Non-blocking observation #2 (scaffolding function/methods redundancy) left as-is per review — it is non-blocking and the review does not require it.
