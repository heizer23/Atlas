# Design Review — EssayCards / Sprint03_Images

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-08-30
**Reviewer:** sprint_design_reviewer

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design is scoped tightly to the draft goal, implements all six locked
  decisions without re-litigating them, and handles the layer question, the split
  durable-state model (R-CON-BP-03), the Dataset / mutation split (R-CON-BP-04), and
  the path-traversal / exposure concerns (R-OPS-BP-02) explicitly and correctly. The
  two carried-forward items (merged-but-unclosed examinations baseline; `-test`
  container missing staging/images mounts) are surfaced per R-OPS-BP-01, correctly
  owner-assigned, and do not block implementation. Two contract/flow gaps remain: the
  scan report's `skipped[].reason` enum is inconsistent across artifacts, and the
  per-file transaction boundary for the scan loop is unspecified in a way that
  conflicts with the documented per-file-failure-and-continue behavior.

## Confirmed Problems

1. **`skipped[].reason` enum is inconsistent across artifacts**
   - Severity: Major
   - Location: `10_architecture.json` §interfaces.exposed_surfaces (`POST /api/essaycards/images/scan`, reason set `'not-an-image'|'format-mismatch'|'gif-too-large'|'too-large'`) vs §internal_flow step 10(f) (`record skipped('error')`) and `10_scaffolding.json` `backend/import_images.py` → `SkippedFile` (`'not-an-image' | 'format-mismatch' | 'gif-too-large' | 'too-large' | 'error'`)
   - Why it is a problem: The endpoint's declared success-response contract enumerates four `reason` values; the internal flow and the scaffold produce a fifth (`'error'`). The declared contract is the authoritative shape for the consumer (the Images view renders `skipped` entries), and it does not cover a value the pipeline can emit. R-CON-BP-11 requires every internal_flow branch to map to an interface-visible behavior; R-CON-BP-08/09 require the contract to be complete and consistent across artifacts.
   - Impact: The Images-view scan report may fail to render or mis-label `skipped` entries with `reason: 'error'`; the test spec (which also lists only four reasons implicitly) gives no coverage target for that branch. `deferred_decisions` item 4 leaves it to the implementer whether `'error'` is ever emitted, so the contract cannot be finalized without either listing it or removing it.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the response enum was written from the image/format skip reasons before the per-file DB-error branch was added to the flow and scaffold.

2. **Per-file transaction/savepoint boundary of the scan loop is unspecified and conflicts with the documented behavior**
   - Severity: Major
   - Location: `10_architecture.json` §internal_flow step 10 (`(f) ... INSERT the essaycards.images row ...; on INSERT failure unlink the file and record skipped('error') (or re-raise ...)`) and the `[NEW]` "Per-file import is atomic" invariant; `10_scaffolding.json` `_import_one` / `_resolve_slug`
   - Why it is a problem: The design states the scan (a) continues after a per-file INSERT failure and (b) resolves an intra-scan slug collision between two never-before-seen files (`10_test_spec.md` "Scan resolves a slug collision"). Both require a defined transaction boundary. `scan_staging(conn)` runs on one psycopg2 connection with default transaction semantics: any failed statement aborts the whole transaction until rollback, so a single `skipped('error')` file poisons every subsequent file; and `_resolve_slug`'s visibility of a prior in-scan INSERT depends on whether the batch is one transaction or one-commit-per-file. "Atomic per file" is stated but never resolved to "commit (or SAVEPOINT) per file". R-CON-BP-10 (step ordering / input sufficiency) and R-CON-BP-11 (behavioral completeness) are not satisfied for the failure and collision branches.
   - Impact: A reasonable single-transaction implementation passes the simple scenarios ("skips a non-image file" skips before any INSERT, so the transaction is never poisoned) but breaks on a mid-scan INSERT failure and can mis-resolve the two-new-files slug collision into a PK conflict → `skipped('error')` for the second file, failing the collision test non-deterministically.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the per-file loop was specified at the level of "write file then insert row" without stating the commit/savepoint boundary that the continue-on-failure and in-scan-collision requirements depend on.

3. **Test spec scenario "Scan skips an oversized GIF" is not represented in the scaffold's test list**
   - Severity: Minor
   - Location: `10_test_spec.md` §Scenarios "### Scan skips an oversized GIF" vs `10_scaffolding.json` `tests/test_images.py` `public_objects` (ten test functions; none targets `gif-too-large`)
   - Why it is a problem: Every other spec scenario has a named test function in the scaffold; this one does not. R-PRO-BP-01 §10 requires each scenario to map to a concrete test function. The `test_writer` deferral ("Map every scenario in 10_test_spec.md to a concrete pytest function") would catch it, but the enumerated list is what a reader checks against.
   - Impact: The `gif-too-large` gate in `_process_image` (GIF byte/edge passthrough logic) may ship without automated coverage.

## Recommended Improvements

1. **Resolve the `[UI]` vs `[UI — manual]` labelling tension**
   - Location: `10_test_spec.md` "### [UI] Review card renders a Markdown image in the answer"; `10_scaffolding.json` §deferrals.ui_implementer (last item)
   - Improvement: Either commit this sprint to standing up the minimal `tests/ui/` Playwright scaffold for this one DOM-level assertion, or relabel the scenario `[UI — manual]` per R-PRO-BP-01 §10.
   - Why: The current plan keeps a hard `[UI]` label while allowing it to be "recorded as untested (not passing)" if infra is not stood up. R-PRO-BP-01 §10 says a UI scenario that cannot execute should be `[UI — manual]`; the straddle leaves the only genuinely new UI behavior permanently unverified.

2. **Specify `scan_staging` behavior for non-regular staging entries**
   - Location: `10_architecture.json` §internal_flow step 10 ("Lists staging_dir non-recursively")
   - Improvement: State that only regular files are processed and how a subdirectory or symlink in `/app/staging` is treated (ignored vs `skipped('not-an-image')`).
   - Why: A directory named `foo.jpg` currently falls through to `_import_one` and `_process_image` with undefined outcome; the read-only staging mount is user-managed and may contain such entries.

3. **Make the images router's `IMAGES_DIR` reference explicitly patch-addressable**
   - Location: `10_scaffolding.json` `backend/routers/images.py`; `10_architecture.json` §deferred_decisions item 3; `10_test_spec.md` §Scope
   - Improvement: Require the router to read `backend.import_images.IMAGES_DIR` at request time (module attribute access) rather than binding it at import, so the documented `tmp_path` monkeypatch is deterministic without patching two module namespaces.
   - Why: `deferred_decisions` leaves the mechanism open, but the "row present / file missing" and "serves bytes" tests depend on the router and the core seeing the same tmp directory.

## Scaffold-Only Observations

1. **`fixtures.sql` deferral wording references a non-existent column**
   - Location: `10_scaffolding.json` `tests/fixtures.sql` role ("add 2-3 essaycards.images rows (ids/slugs prefixed `fix-img-`)"); also §deferrals.application_implementer
   - Observation: `essaycards.images` has no `id` column — `slug` is the primary key. The fixtures only need `slug` values (`fix-img-alpha`, `fix-img-beta`) plus `stored_filename`.
   - Impact on implementation: Cosmetic; implementer must not add an `id` column or expect one.

2. **Sprint `10_schema.sql` reproduces the full runtime schema**
   - Location: `Sprint03_Images/10_schema.sql`; `10_architecture.json` §persistence.notes
   - Observation: Only `03_Application/EssayCards/schema.sql` is loaded at startup and by `tests/conftest.py`; the sprint file is documentary. The five pre-existing tables in `10_schema.sql` currently match `schema.sql` byte-for-byte.
   - Impact on implementation: The images DDL must be folded into `03_Application/EssayCards/schema.sql` verbatim (including the R-CON-BP-03 comment) before the closing `commit;`; the sprint artifact must not be wired into any load path (R-CON-BP-07 canonical path is `03_Application/EssayCards/schema.sql`).

## Hard Rule Violations

None identified.

## Open Uncertainties

1. **Merged-but-unclosed oral-examinations baseline**
   - Location: `10_architecture.json` §risks (last entry) and §open_questions (owner: architecture)
   - Uncertainty: The examinations router/table/tests are live in the running service and in `CLAUDE.md` but absent from the seed `00_architecture/` snapshot and from `atlas_dev_ref.md`; there is no closed sprint folder for that work.
   - Why it matters: The image changes are independent of examinations (no shared tables or endpoints, only a cited docstring precedent), so this does not block implementation. It does mean `/sprint-close` must regenerate `00_architecture/` and `atlas_dev_ref.md` from the combined examinations + images state, or the developer reference will keep understating the API surface.
   - Suggested owner: Architecture

2. **`-test` container has no `/app/staging` or `/app/images` mount**
   - Location: `10_architecture.json` §open_questions (owner: implementer); `10_test_spec.md` §Scope
   - Uncertainty: Confirm the test strategy is monkeypatching `STAGING_DIR` / `IMAGES_DIR` (core and router) to `tmp_path` with no `compose.yml` change for the `-test` service.
   - Why it matters: The approach is sound and the spec is written around it; the residual risk is only a noisy test failure if the monkeypatch target is wrong (see Recommended Improvement 3), not a silent pass.
   - Suggested owner: Implementer

## Minimal Change Set

1. Make `skipped[].reason` a single enum used identically in `10_architecture.json`
   (exposed_surfaces + internal_flow step 10), `10_scaffolding.json` (`SkippedFile`),
   and `10_test_spec.md` — either add `'error'` to the endpoint contract or remove the
   `'error'` branch from the flow and scaffold.
2. In `10_architecture.json` internal_flow step 10 and the `[NEW]` per-file-atomicity
   invariant, state the per-file transaction boundary: each file is committed (or
   wrapped in a SAVEPOINT) independently, so a per-file INSERT failure neither aborts
   the remaining batch nor rolls back already-imported files, and `_resolve_slug` sees
   prior in-scan inserts.
3. Add a `tests/test_images.py` function for the "Scan skips an oversized GIF"
   (`gif-too-large`) scenario to `10_scaffolding.json`.

## Approval Condition

All three Minimal Change Set items are applied and the `skipped[].reason` enum is
identical across `10_architecture.json`, `10_scaffolding.json`, and `10_test_spec.md`.
