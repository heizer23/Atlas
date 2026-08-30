# Design Corrections — EssayCards / Sprint03_Images

## Applied Changes

1. **`skipped[].reason` enum made canonical and identical across artifacts**
   - Review Source: `11_design_review.md` §Minimal Change Set item 1; §Confirmed Problems item 1 (Major)
   - Files Updated: `10_architecture.json`, `10_test_spec.md` (`10_scaffolding.json` `SkippedFile` already carried the full set — left as-is)
   - Change: Resolved the four-vs-five inconsistency by making `'error'` part of the
     canonical set (retention, not removal). The endpoint success-response contract in
     `10_architecture.json` §interfaces.exposed_surfaces (`POST /api/essaycards/images/scan`)
     now enumerates `'not-an-image'|'format-mismatch'|'gif-too-large'|'too-large'|'error'`,
     matching `10_scaffolding.json` `backend/import_images.py` → `SkippedFile`. `10_test_spec.md`
     §Scope now states the same five-value set explicitly. Retention (rather than removal) is
     the only reading consistent with Minimal Change Set item 2, which mandates a
     per-file INSERT failure be recorded and the batch continue — i.e. it must map to a
     `skipped` reason (`'error'`), satisfying R-CON-BP-11.

2. **Per-file transaction boundary of the scan loop specified (savepoint per file)**
   - Review Source: `11_design_review.md` §Minimal Change Set item 2; §Confirmed Problems item 2 (Major)
   - Files Updated: `10_architecture.json`, `10_scaffolding.json`
   - Change: `10_architecture.json` §internal_flow step 10(f) now specifies: each file is
     processed inside its own `SAVEPOINT`; on a successful INSERT the savepoint is released
     and the row committed before the next file (so already-imported files are never rolled
     back and their slugs are visible to `_resolve_slug` for later files in the same scan);
     on INSERT failure the loop does `ROLLBACK TO` that savepoint (preventing psycopg2 from
     leaving the whole transaction aborted), unlinks the just-written file, records
     `skipped('error')`, and continues; only a connection-level failure re-raises as
     `ImportInfraError`. The `[NEW]` "Per-file import is atomic" invariant was updated to
     the same boundary ("atomic and independently committed"). `deferred_decisions` item 4
     was narrowed to commit-granularity only (the observable boundary is now fixed, not
     deferred). `10_scaffolding.json` reflects this in `backend/import_images.py` module
     role, `scan_staging` purpose, and `_import_one` purpose.

3. **Unmapped test scenario "Scan skips an oversized GIF" given a scaffold function**
   - Review Source: `11_design_review.md` §Minimal Change Set item 3; §Confirmed Problems item 3 (Minor)
   - Files Updated: `10_scaffolding.json`
   - Change: Added `test_scan_skips_oversized_gif` to `tests/test_images.py` `public_objects`
     (purpose "Scenario: Scan skips an oversized GIF"), positioned between
     `test_scan_skips_non_image_file_and_continues` and
     `test_scan_slug_collision_appends_hash_suffix` to match the spec ordering.

## Unchanged by Design

- All other sections of `10_architecture.json`, `10_scaffolding.json`, and `10_test_spec.md`
  were preserved verbatim: the endpoint list and the other two endpoints' contracts, the
  slug/dedupe/normalize invariants, persistence and schema references (`10_schema.sql`
  untouched — no finding required it), the Dataset/mutation split, path-traversal guard,
  UI deferrals, risks, and open questions. Recommended Improvements and Scaffold-Only
  Observations from the review were not applied (not in the Minimal Change Set, not marked
  required before implementation).

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — all three Minimal Change Set items applied; the
  `skipped[].reason` set (`not-an-image`, `format-mismatch`, `gif-too-large`, `too-large`,
  `error`) is now identical across `10_architecture.json`, `10_scaffolding.json`, and
  `10_test_spec.md`.
- Notes: The review left item 1 as an either/or (add `'error'` vs. remove it). It was
  resolved by retention, because Minimal Change Set item 2 requires an INSERT-failure to
  be recorded-and-continue, which has no interface-visible landing spot other than a
  `skipped` reason. No dedicated test scenario/function was added for the `'error'`
  branch — Minimal Change Set item 3 names only the oversized-GIF scenario, and adding
  `'error'` coverage would exceed the approved change set. If the team wants that
  coverage, it should be a follow-up spec item.
