# Design Corrections — essaycards (Sprint03_Images)

## Applied Changes

1. **`deferred_decisions` item 4 reconciled with the fixed per-file transaction boundary**
   - Review Source: `13_design_review.md` §Confirmed Problems item 1 (Major); §Minimal Change Set item 1 (option a); §Approval Condition
   - Files Updated: `10_architecture.json`
   - Change: Rewrote `deferred_decisions` item 4. It previously stated commit granularity was
     "the implementer's choice (per-file SAVEPOINTs with a single commit after the batch, vs.
     an explicit commit after each file)". It now states the transaction shape is fixed, not
     deferred, and describes exactly one shape: one SAVEPOINT per file; on a successful INSERT
     RELEASE the SAVEPOINT and commit that file's row before the next file; on an INSERT
     failure ROLLBACK TO that file's SAVEPOINT, unlink the just-written file, record
     `skipped('error')`, and continue; a connection-level failure re-raises as
     `ImportInfraError`. The "single commit after the batch" alternative is explicitly
     removed. The wholesale staging/images-dir `ImportInfraError` remains mandatory. The only
     residual implementer latitude is the psycopg2 call style used to issue the
     SAVEPOINT/RELEASE/ROLLBACK-TO statements, which may not change the observable boundary.
     This makes item 4 identical in substance to `internal_flow` step 10(f) and the `[NEW]
     Per-file import is atomic and independently committed` invariant.

2. **`skipped('error')` branch given an explicit no-automated-coverage note**
   - Review Source: `13_design_review.md` §Recommended Improvements item 1 (Non-blocking); applied per orchestrator instruction, lighter of the two offered options
   - Files Updated: `10_test_spec.md`
   - Change: Added two sentences to §Scope stating that the `error` reason path (a per-file
     INSERT failure rolled back to the file's savepoint so the batch continues) is
     deliberately left to manual/inspection coverage this sprint and has no dedicated
     automated scenario, while the other four `skipped[].reason` values each have a scan
     scenario. No new test function was added to `10_scaffolding.json` `tests/test_images.py`.

## Unchanged by Design

- `10_architecture.json` `internal_flow` step 10(f) and the `[NEW] Per-file import is atomic
  and independently committed` invariant were already corrected in `12_design_corrections.md`
  to the exact per-file-commit shape the review now requires everywhere; they were left
  verbatim (no contradiction remained in them — only `deferred_decisions` item 4 dissented).
- `10_scaffolding.json` `backend/import_images.py` `_import_one` and `scan_staging` purposes
  already describe the same single transaction shape (per-file SAVEPOINT, RELEASE + commit
  that row before the next file, ROLLBACK TO on INSERT failure with `SkippedFile('error')`
  and batch continuation, `ImportInfraError` only on wholesale staging/images-dir or
  connection-level failure); they were left verbatim.
- `10_schema.sql` was not touched (the review required no schema change).
- All other sections of `10_architecture.json`, `10_scaffolding.json`, and `10_test_spec.md`
  (endpoint contracts, the five-value `skipped[].reason` enum, slug/dedupe/normalize
  invariants, persistence and schema references, the Dataset/mutation split, path-traversal
  guard, UI deferrals, risks, open questions, and all test scenarios and mapped functions)
  were preserved verbatim. Scaffold-Only Observations and Open Uncertainties from the review
  were not actioned — they are outside the Minimal Change Set and not marked required before
  implementation.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — `10_architecture.json` §deferred_decisions item 4,
  §internal_flow step 10(f), the per-file-atomicity invariant, and `10_scaffolding.json`
  (`_import_one`, `scan_staging`) now all describe exactly one per-file transaction shape
  with no residual "implementer's choice" between per-file commit and batch commit.
- Notes: The non-blocking Recommended Improvement was resolved with an explicit no-coverage
  note in `10_test_spec.md` §Scope (the lighter option the review permitted); if the team
  later wants an automated `skipped('error')` scenario, that is a follow-up spec item.
