# Design Corrections — StoryReader (Sprint01_Core)

## Applied Changes

1. **Missing Atlas Shell consumer-wiring instruction (main.tsx side-effect import)**
   - Review Source: `11_design_review.md` §Confirmed Problems #1, §Minimal Change Set #1
   - Files Updated: `10_architecture.json`, `10_scaffolding.json`
   - Change: Added an explicit instruction to `10_architecture.json §deferrals.ui_implementer` directing the implementer to add `import '../../../../03_Application/StoryReader/src/shellConfig';` to `02_Platform/Atlas_Shell/src/shell/main.tsx`'s "REGISTER APPLICATION SHELLS" block, matching the exact per-app import shape already used by every registered app (verified against `main.tsx:40-49`, e.g. StorageTracker's mobilePrimaryNav import). Extended `10_architecture.json §risks[1]` (previously covering only `nginx.conf` + `STORYREADER_CONTENT_DIR`) to also name the `main.tsx` import as the same class of easy-to-forget out-of-component edit, with matching impact text. Added `10_scaffolding.json §main_tsx_note`, structurally parallel to the existing `§nginx_note`, documenting the same instruction since it lives outside `03_Application/StoryReader`. No line was added to the actual `main.tsx` file — consistent with how the pre-existing, structurally identical `nginx.conf` edit is handled (documented instruction for the implementer, not performed during design).

2. **Hard rule violation — Dataset row missing required `id` field (R-CON-BP-04)**
   - Review Source: `11_design_review.md` §Hard Rule Violations #1, §Minimal Change Set #2
   - Files Updated: `10_architecture.json`, `10_scaffolding.json`
   - Change: Added `id` (the resolved version's own `story_versions.id`) to the `GET /api/storyreader/stories/{story_id}/versions/{version}` row shape in `10_architecture.json §interfaces.exposed_surfaces`, and updated `§internal_flow[4]` ("get_version_content")'s description to state that the fetched `story_versions` row's `id` column becomes the response row's `id` field. Updated the corresponding `backend/routers/stories.py::get_version_content` stub purpose text in `10_scaffolding.json` to state the same. `10_schema.sql` required no change — `story_versions.id` already exists as the table's primary key.

## Unchanged by Design
All other sections of `10_architecture.json` and `10_scaffolding.json` — including the paragraph-split algorithm, context-window rule, reaction semantics, all other endpoints' row shapes, `internal_flow` steps 1–4 and 6–11, `dependencies`, `persistence`, the remaining `deferrals` entries, and all other `10_scaffolding.json` file stubs — are preserved verbatim. `10_schema.sql` and `10_test_spec.md` were not modified.

## Review Alignment Check
- Minimal Change Set Applied: Partially — items 1 and 2 (the two items backed by the review's Approval Condition) are applied in full. Item 3 (adding two missing `POST /annotations` failure-mode scenarios to `10_test_spec.md`) was explicitly out of scope for this correction pass per the requesting instructions, and is not required by the review's stated Approval Condition.
- Approval Condition Satisfied: Yes — both conditions in `11_design_review.md §Approval Condition` ((a) explicit `main.tsx` side-effect import instruction, (b) `id` field on the `GET .../versions/{version}` Dataset row) are now reflected consistently across `interfaces.exposed_surfaces`, `internal_flow`, and the scaffolding file stubs/notes.
- Notes: Minimal Change Set item 3 (`10_test_spec.md` scenario additions, tied to a Recommended Improvement rather than a Confirmed Problem or Hard Rule Violation) remains open. It does not block the Approval Condition as written but should be tracked before `10_test_spec.md` is treated as the final traceability source for the test_writer deferral.
