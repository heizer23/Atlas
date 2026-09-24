# Design Review — StoryReader (Sprint01_Core)

## Verdict
- Status: APPROVED
- Summary: Both corrections from `12_design_corrections.md` were independently verified against the live artifacts — the `main.tsx` side-effect import instruction and the `id` field on the `GET .../versions/{version}` Dataset row — and both are applied correctly and consistently across `10_architecture.json` and `10_scaffolding.json`. The main.tsx import path was additionally checked against the real `02_Platform/Atlas_Shell/src/shell/main.tsx` file and matches the exact pattern used by every currently-registered app. No regression was introduced elsewhere in the design.

## Confirmed Problems
None identified.

## Recommended Improvements
None identified. (The two items from `11_design_review.md §Recommended Improvements` — missing `POST /annotations` failure-mode scenarios in `10_test_spec.md`, and `internal_flow[6]`'s inputs omission — remain open per `12_design_corrections.md §Review Alignment Check`, which correctly notes they were never part of the prior Approval Condition. Not re-raised here to avoid duplicating an already-tracked, non-blocking item.)

## Scaffold-Only Observations
None identified beyond the one already on record in `11_design_review.md` (untouched by this correction round: `tests/` directory has no `conftest.py`/`fixtures.sql` stub entries).

## Hard Rule Violations
None identified. Verified directly:
- `10_architecture.json §interfaces.exposed_surfaces` — `GET .../versions/{version}` `row_shape` now reads `{ id (uuid — the resolved version's own story_versions.id, required per R-CON-BP-04's Dataset row identity rule), story_id, version, title, paragraphs: [...], created_at }`. Satisfies R-CON-BP-04 / `UI_Data_Contract.md §2`.
- `10_architecture.json §internal_flow[4]` ("get_version_content") description now states the fetched `story_versions` row's `id` becomes the response row's `id`, matching the row_shape above.
- `10_scaffolding.json §files` — `backend/routers/stories.py::get_version_content` purpose text states the same `id`-mapping behavior, matching both `10_architecture.json` locations.
- `10_schema.sql` correctly required no change — `storyreader.story_versions.id` already exists as the table's `uuid primary key default gen_random_uuid()` (line 26).

## Open Uncertainties
1. **Component rename timing** (carried over, unchanged)
   - Location: `10_architecture.json §naming_note`, `§open_questions[0]`
   - Uncertainty: Whether/when the human executes the `StoryReader` → `Marginalia` (or other) rename relative to implementation.
   - Why it matters: Low risk, cosmetic only; already correctly flagged per R-OPS-BP-01.
   - Suggested owner: Product

2. **Final `STORYREADER_CONTENT_DIR` host path and future ingestion trigger** (carried over, unchanged)
   - Location: `10_architecture.json §open_questions[1]`, `§deferrals.application_implementer`
   - Uncertainty: Real host-side content directory location; whether ingestion gains an automated trigger later.
   - Why it matters: Low risk this sprint — isolated to a compose-only env var never read by application code.
   - Suggested owner: Product

## Minimal Change Set
None — no further changes required for approval.

## Approval Condition
None — approved as-is.
