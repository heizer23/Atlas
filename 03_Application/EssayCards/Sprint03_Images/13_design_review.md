# Design Review — EssayCards / Sprint03_Images

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-08-30
**Reviewer:** sprint_design_reviewer
**Review pass:** 2 (re-review after `12_design_corrections.md`)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: Two of the three prior findings are fully resolved. Finding 1
  (`skipped[].reason` enum) is now a single five-value set — `not-an-image |
  format-mismatch | gif-too-large | too-large | error` — identical across the
  `10_architecture.json` endpoint contract, `10_scaffolding.json` `SkippedFile`, and
  `10_test_spec.md` §Scope. Finding 3 (`test_scan_skips_oversized_gif`) is now present in
  the scaffold's `tests/test_images.py` list. Finding 2 (per-file SAVEPOINT boundary) is
  substantively resolved in `internal_flow` step 10, the per-file-atomicity invariant, and
  the scaffold — but the correction left `deferred_decisions` item 4 offering a commit
  granularity ("a single commit after the batch") that contradicts the now-normative
  "commit that file's row before moving to the next file" it elsewhere fixes. That is a
  single R-CON-BP-09 cross-artifact inconsistency and the only remaining blocker. No other
  regression was introduced by the corrections.

## Confirmed Problems

1. **`deferred_decisions` item 4 contradicts the per-file-commit boundary it defers to**
   - Severity: Major
   - Location: `10_architecture.json` §deferred_decisions item 4 vs §internal_flow step 10(f)
     and §contracts.invariants (the `[NEW] Per-file import is atomic and independently
     committed` invariant); `10_scaffolding.json` `backend/import_images.py` →
     `_import_one` purpose and `scan_staging` purpose
   - Why it is a problem: `deferred_decisions` item 4 states commit granularity is "the
     implementer's choice (per-file SAVEPOINTs with a single commit after the batch, vs. an
     explicit commit after each file) … as long as the internal_flow step 10 boundary
     holds." But `internal_flow` step 10(f) mandates "on a successful INSERT RELEASE the
     SAVEPOINT and commit that file's row before moving to the next file, so already-imported
     files are never rolled back by a later per-file failure," and the invariant states
     "the SAVEPOINT is released and that row is committed before the next file" and "because
     prior in-scan imports are already committed, `_resolve_slug` sees their slugs." The
     "single commit after the batch" option contradicts the very constraint item 4 claims to
     respect. R-CON-BP-09 (a decision concretely expressed in one artifact section must be
     reflected identically in all others) and R-CON-BP-08 (a contract must be unambiguous
     without cross-referencing) are both unsatisfied.
   - Impact: An implementer following item 4's "single commit after the batch" reading
     produces a transaction shape in which the invariant's stated mechanism ("prior in-scan
     imports are already committed") is factually false, and step 10's guarantee that
     "already-imported files are never rolled back" no longer holds on a connection-level
     failure mid-scan. The design does not deterministically say which of the two
     transaction shapes is authoritative, so `50_test_report.md` cannot attribute a future
     partial-batch failure to a spec.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the correction fixed the
     SAVEPOINT boundary in `internal_flow` and the invariant but left the pre-correction
     "granularity is deferred" sentence in place, so the deferral now points at a constraint
     that forbids one of its own listed options.

## Recommended Improvements

1. **Give `skipped[].reason: 'error'` an explicit coverage target or an explicit no-coverage note**
   - Location: `10_test_spec.md` §Scenarios; `10_scaffolding.json` `tests/test_images.py`
     `public_objects`
   - Improvement: Add one scenario/function exercising a per-file INSERT failure that yields
     `skipped('error')` and continues the batch, or state in `10_test_spec.md` §Scope that
     the `'error'` branch is deliberately left to manual/inspection coverage this sprint.
   - Why: `11_design_review.md` Confirmed Problem 1 already noted the `'error'` branch "gives
     no coverage target"; the correction retained `'error'` as a canonical, reachable
     contract value but added no scenario. R-CON-BP-11 expects every interface-visible
     behavior to have a coverage anchor; a DB-INSERT-failure branch is easy to regress
     silently. `12_design_corrections.md` itself flags this as a candidate follow-up.

## Scaffold-Only Observations

1. **`fixtures.sql` deferral still references a non-existent `id` column** (unchanged from
   `11_design_review.md` §Scaffold-Only Observations 1; not touched by the corrections)
   - Location: `10_scaffolding.json` `tests/fixtures.sql` role and
     §deferrals.application_implementer ("add 2-3 essaycards.images rows (ids/slugs prefixed
     `fix-img-`)")
   - Observation: `essaycards.images` (`10_schema.sql:113-127`) has `slug` as the primary
     key and no `id` column. Fixtures need `slug` values (`fix-img-alpha`, `fix-img-beta`)
     plus `stored_filename`, `content_type`, `byte_size`, `source_sha256`, `source_filename`,
     and ordered `created_at`.
   - Impact on implementation: Cosmetic; the implementer must not add or expect an `id`
     column. Advisory only — outside the approved change set.

## Hard Rule Violations

None identified. (The R-CON-BP-09 / R-CON-BP-08 conflict is captured as Confirmed Problem 1
with its required fix in the Minimal Change Set.)

## Open Uncertainties

1. **Merged-but-unclosed oral-examinations baseline** (carried forward from
   `11_design_review.md`; not affected by the corrections)
   - Location: `10_architecture.json` §risks (last entry) and §open_questions (owner:
     architecture)
   - Uncertainty: The examinations router/table/tests are live in the running service and in
     `CLAUDE.md` but absent from the seed `00_architecture/` snapshot and from
     `atlas_dev_ref.md` (which lists only the five pre-image EssayCards endpoints).
   - Why it matters: The image changes share no tables or endpoints with examinations (only
     a cited docstring precedent), so this does not block implementation. `/sprint-close`
     must regenerate `00_architecture/` and `atlas_dev_ref.md` from the combined examinations
     + images state or the developer reference will keep understating the API surface.
   - Suggested owner: Architecture

2. **`-test` container has no `/app/staging` or `/app/images` mount** (carried forward from
   `11_design_review.md`; not affected by the corrections)
   - Location: `10_architecture.json` §open_questions (owner: implementer);
     `10_test_spec.md` §Scope
   - Uncertainty: Confirm the test strategy is monkeypatching `STAGING_DIR` / `IMAGES_DIR`
     (import core and images router) to `tmp_path` with no `compose.yml` change for the
     `-test` service.
   - Why it matters: The approach is sound and the spec is written around it; residual risk
     is a noisy test failure if the monkeypatch target is wrong, not a silent pass.
   - Suggested owner: Implementer

## Minimal Change Set

1. Reconcile `10_architecture.json` §deferred_decisions item 4 with the fixed per-file
   transaction boundary — either (a) remove the "per-file SAVEPOINTs with a single commit
   after the batch" alternative and state that an explicit commit after each successful
   INSERT is required, or (b) reword §internal_flow step 10(f) and the `[NEW] Per-file
   import is atomic and independently committed` invariant to require only per-file
   SAVEPOINT release (dropping "committed before the next file" and "already committed") so
   both readings agree.
2. Make `10_scaffolding.json` `backend/import_images.py` `_import_one` and `scan_staging`
   purposes describe the same single transaction shape chosen in item 1.

## Approval Condition

`10_architecture.json` §deferred_decisions item 4, §internal_flow step 10(f), the
per-file-atomicity invariant, and `10_scaffolding.json` (`_import_one`, `scan_staging`) all
describe exactly one per-file transaction shape with no residual "implementer's choice"
between per-file commit and batch commit.
