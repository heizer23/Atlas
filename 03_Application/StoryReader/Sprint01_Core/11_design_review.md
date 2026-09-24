# Design Review — StoryReader (Sprint01_Core)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design correctly resolves all four items the draft left open (paragraph-split algorithm, context window bound, slug-vs-story_id resolution, dedicated content-mount env var) with explicit, cross-artifact-consistent rules, and the placeholder-name deferral is an acceptable, explicitly-flagged human follow-up. Two concrete, narrow defects must be corrected before implementation: a missing Atlas Shell wiring instruction (main.tsx side-effect import) and a Dataset row missing its required `id` field on one endpoint. Both are small, well-scoped fixes, not a redesign.

## Confirmed Problems

1. **Missing Atlas Shell consumer-wiring instruction (main.tsx side-effect import)**
   - Severity: Major
   - Location: `03_Application/StoryReader/Sprint01_Core/10_scaffolding.json` (files list has no entry or note for `02_Platform/Atlas_Shell/src/shell/main.tsx`); `10_architecture.json §deferrals.application_implementer` and `§deferrals.ui_implementer` (neither lists this edit)
   - Why it is a problem: `02_Platform/Atlas_Shell/src/shell/main.tsx`'s own header comment defines the actual consumption mechanism (R-CON-BP-06): every application's `shellConfig.ts` is loaded only via an explicit side-effect import added to `main.tsx` ("2. Add a side-effect import below"). Confirmed against every currently-registered app (`WorkoutTracker`, `TaskTracker`, ..., `ClaudeConsole` at `main.tsx:40-49`) — none is reachable without this line. Neither `10_architecture.json` nor `10_scaffolding.json` instructs the implementer to add it, even though the design explicitly flagged the structurally identical out-of-component edit for `nginx.conf` (`10_architecture.json §risks[1]`, `§deferrals.application_implementer`, `10_scaffolding.json §nginx_note`).
   - Impact: Without this one-line edit, `AppRegistry.register()` for `storyreader` never executes, so the app is never listed by `AppRegistry.getAll()`/`getByPath()` — the Story list, Reader, and Feedback list are all unreachable through the shell despite a healthy backend and a correctly built frontend bundle.
   - Likely Cause (Design Phase): Dependency Misinterpretation — the design correctly modeled the `AppRegistry.register()` call shape itself (scaffolded in `src/shellConfig.ts`) but did not trace the full wiring chain that activates it, even though the same class of cross-component edit (nginx.conf) was correctly identified and flagged elsewhere in the same document.

## Recommended Improvements

1. **Two POST /annotations failure modes are undeclared in the test spec**
   - Location: `10_test_spec.md §Scenarios` vs. `10_architecture.json §contracts.failure_modes`
   - Improvement: Add scenarios for "`paragraph_index` outside range for that version" and "`char_end` exceeds the paragraph's rendered text length" — both are declared failure modes in `10_architecture.json` but have no corresponding scenario, unlike the other seven POST /annotations failure modes which are all covered.
   - Why: `10_test_spec.md` is the traceability link the test_writer deferral (`10_architecture.json §deferrals.test_writer`) uses to enumerate concrete pytest functions; a failure mode with no scenario is more likely to go untested even though it is already specified.

2. **internal_flow step 7's declared inputs omit the DB fetch it depends on**
   - Location: `10_architecture.json §internal_flow[6]` ("create_or_update_annotation")
   - Improvement: Add "the target version's `story_versions` row (`body_markdown`, fetched by `story_id`+`version`)" to the step's `inputs` array, alongside the POST body fields already listed.
   - Why: The step's own description text calls `split_paragraphs(that version's body_markdown)` for bounds validation, so the DB fetch is a real, load-bearing input (R-CON-BP-10) that the formal `inputs` list currently omits, unlike steps 5 and 6 which declare their DB dependency inputs explicitly.

## Scaffold-Only Observations

1. **`tests/` directory scaffolded with no test-file stubs**
   - Location: `10_scaffolding.json §directories` (`03_Application/StoryReader/tests`) vs. `§files`
   - Observation: Every backend module (`database.py`, `paragraphs.py`, `ingest.py`, `routers/stories.py`, `main.py`) has an individual stub entry under `files`, but no `tests/conftest.py` or `tests/fixtures.sql` stub is listed, even though `10_architecture.json §deferrals.test_writer` and `§deferrals.reviewer` both assume the StorageTracker/EssayCards `conftest.py` + `fixtures.sql` convention.
   - Impact on implementation: Minor — the convention is well-established elsewhere in the codebase and documented in the deferrals text, so this is unlikely to cause a wrong implementation, only a slightly less complete scaffold than the backend modules receive.

## Hard Rule Violations

1. **Dataset row missing required `id` field**
   - Rule Source: `.claude/rules/R-CON-BP.md` (R-CON-BP-04); `02_Platform/Atlas_Shell/platform-ui/api/UI_Data_Contract.md §2` ("Every row must have an id field (string) | WarningPlaceholder if missing")
   - Location: `10_architecture.json §interfaces.exposed_surfaces` — `GET /api/storyreader/stories/{story_id}/versions/{version}`, `row_shape`
   - Violation: The declared row shape is `{ story_id, version, title, paragraphs: [...], created_at }` — no `id` field. This endpoint's `ui_contract` is declared `Dataset | ApiError` (not exempt under the mutation-endpoint carve-out), so its row must satisfy the platform `Row` type (`{ id: string } + ...`) per the contract authority files (`platform_contracts/contracts.py`, `platform-ui/api/types.ts`). Every other Dataset-returning endpoint in this same design (`GET /stories`, `GET /stories/{story_id}`, `GET .../annotations`) correctly includes `id`; this is the sole omission.
   - Required Fix: Add `id` (the version row's own surrogate uuid, `story_versions.id`) to the row shape in `10_architecture.json §interfaces.exposed_surfaces` and `§internal_flow[4]` ("get_version_content"), and to the `backend/routers/stories.py` stub's described return shape in `10_scaffolding.json`.

## Open Uncertainties

1. **Component rename timing**
   - Location: `10_architecture.json §naming_note`, `§open_questions[0]`
   - Uncertainty: Whether/when the human executes `git mv 03_Application/StoryReader 03_Application/Marginalia` (or another name) relative to this sprint's implementation.
   - Why it matters: Low risk — cosmetic only, does not affect any contract, endpoint, or schema in this design. Explicitly and correctly flagged per R-OPS-BP-01 as a human-actionable deferral rather than silently done or silently skipped; not a design defect.
   - Suggested owner: Product

2. **Final `STORYREADER_CONTENT_DIR` host path and future ingestion trigger**
   - Location: `10_architecture.json §open_questions[1]`, `§deferrals.application_implementer`
   - Uncertainty: The real host-side content directory location, and whether ingestion remains a manual `docker exec` call or gains an automated trigger (e.g. filesystem watcher) in a later sprint.
   - Why it matters: Low risk this sprint — the design already isolates this to a compose-only env var never read by application code (`STORYREADER_CONTENT_DIR`), so any placeholder host path works until the real one is known; no code change is required when it is decided.
   - Suggested owner: Product

## Minimal Change Set
1. Add `import '../../../../03_Application/StoryReader/src/shellConfig';` to `02_Platform/Atlas_Shell/src/shell/main.tsx`'s "REGISTER APPLICATION SHELLS" block, and add this instruction to `10_architecture.json §deferrals.application_implementer` (or `§deferrals.ui_implementer`) and to `10_scaffolding.json` (a note parallel to the existing `nginx_note`).
2. Add an `id` field (the version's own `story_versions.id`) to the `GET .../versions/{version}` row shape in `10_architecture.json §interfaces.exposed_surfaces` and `§internal_flow[4]`, and to the `backend/routers/stories.py` stub in `10_scaffolding.json`.
3. Add the two missing POST /annotations failure-mode scenarios (paragraph_index out of range; char_end exceeds paragraph length) to `10_test_spec.md`.

## Approval Condition
`10_architecture.json` and `10_scaffolding.json` are corrected to (a) explicitly instruct adding the `main.tsx` side-effect import for `storyreader`'s `shellConfig.ts`, and (b) add an `id` field to the `GET .../versions/{version}` Dataset row shape, with both corrections reflected consistently across `interfaces.exposed_surfaces`, `internal_flow`, and the scaffolding file stubs.
