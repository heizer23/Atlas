# Design Review — EssayCards / Sprint03_Images

**Verdict:** APPROVED
**Date:** 2026-08-30
**Reviewer:** sprint_design_reviewer
**Review pass:** 3 (re-review after `14_design_corrections.md`)

## Verdict
- Status: APPROVED
- Summary: The one remaining blocker from `13_design_review.md` — `deferred_decisions`
  item 4 still offering "single commit after the batch" as an implementer choice — is
  fully resolved. All four locations (`deferred_decisions` item 4, `internal_flow`
  step 10(f), the `[NEW]` per-file-atomicity invariant, and `10_scaffolding.json`
  `_import_one` / `scan_staging` / module role) now describe exactly one per-file
  transaction shape: one SAVEPOINT per file; success → RELEASE + commit that row
  before the next file; INSERT failure → ROLLBACK TO SAVEPOINT, unlink, `skipped('error')`,
  continue; connection-level failure → `ImportInfraError`. The only residual latitude is
  psycopg2 call style, which cannot change the observable boundary. The non-blocking
  recommendation (an explicit coverage decision for the `skipped('error')` branch) was
  addressed in `10_test_spec.md` §Scope. A light R-CON-BP-09 pass over the whole design
  found no regression. The design is ready for implementation.

## Confirmed Problems
None identified.

The `13_design_review.md` blocker is closed. Verification detail:
- `10_architecture.json` §deferred_decisions item 4 now opens "The per-file import loop's
  transaction shape is fixed, not deferred" and states "No 'single commit after the batch'
  alternative is permitted." The per-file-vs-batch implementer choice is gone.
- `10_architecture.json` §internal_flow step 10(f) and the `[NEW] Per-file import is
  atomic and independently committed` invariant (contracts.invariants) describe the same
  shape verbatim in substance: SAVEPOINT per file, RELEASE + commit before the next file,
  ROLLBACK TO on INSERT failure with `skipped('error')` and batch continuation,
  `ImportInfraError` only on wholesale staging/images-dir or connection-level failure.
- `10_scaffolding.json` `backend/import_images.py` module `role`, `scan_staging` purpose,
  and `_import_one` purpose all state the identical boundary.

## Recommended Improvements
None identified.

## Scaffold-Only Observations
1. **`fixtures.sql` deferral wording still references a non-existent `id` column**
   - Location: `10_scaffolding.json` `tests/fixtures.sql` role and
     §deferrals.application_implementer ("add 2-3 essaycards.images rows (ids/slugs
     prefixed `fix-img-`)")
   - Observation: `essaycards.images` (`10_schema.sql:113-127`) has `slug` as the primary
     key and no `id` column. Fixture rows need `slug` values plus `stored_filename`,
     `content_type`, `byte_size`, `source_sha256`, `source_filename`, and ordered
     `created_at`. Carried forward from `11_` and `13_` reviews; advisory only, outside
     the approved change set.
   - Impact on implementation: Cosmetic; the implementer must not add or expect an `id`
     column.

## Hard Rule Violations
None identified.

## Open Uncertainties
1. **Merged-but-unclosed oral-examinations baseline** (carried forward; not affected by
   the corrections)
   - Location: `10_architecture.json` §risks (last entry) and §open_questions (owner:
     architecture)
   - Uncertainty: The examinations router/table/tests are live in the running service and
     in `CLAUDE.md` but absent from the seed `00_architecture/` snapshot and from
     `atlas_dev_ref.md`.
   - Why it matters: The image changes share no tables or endpoints with examinations
     (only a cited docstring precedent), so this does not block implementation.
     `/sprint-close` must regenerate `00_architecture/` and `atlas_dev_ref.md` from the
     combined examinations + images state.
   - Suggested owner: Architecture

2. **`-test` container has no `/app/staging` or `/app/images` mount** (carried forward;
   not affected by the corrections)
   - Location: `10_architecture.json` §open_questions (owner: implementer);
     `10_test_spec.md` §Scope
   - Uncertainty: Confirm the test strategy is monkeypatching `STAGING_DIR` / `IMAGES_DIR`
     (import core and images router) to `tmp_path` with no `compose.yml` change for the
     `-test` service.
   - Why it matters: The approach is sound and the spec is written around it; residual
     risk is a noisy test failure if the monkeypatch target is wrong, not a silent pass.
   - Suggested owner: Implementer

## Minimal Change Set
None — approved as-is.

## Approval Condition
None — approved as-is. The sprint may move to implementation
(`DESIGN_APPROVED` → `sprint_implement`).
