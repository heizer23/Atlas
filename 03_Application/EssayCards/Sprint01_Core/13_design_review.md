# Design Review — EssayCards

## Verdict
- Status: APPROVED
- Summary: Both Major issues from `11_design_review.md` are correctly and coherently resolved in the current artifacts. The `POST .../review` endpoint now performs manual raw-body validation with no Pydantic body model, closing the missing/wrong-typed/unparsable-JSON gaps, not just the out-of-set-value case; the `platform_errorhandling` path is now consistent everywhere it is referenced. No new inconsistency was introduced by the correction. Design is approved for implementation.

## Confirmed Problems
None identified.

## Recommended Improvements
1. **Stale `pydantic` dependency role description**
   - Location: `10_architecture.json` §dependencies.external_required (`{"name": "pydantic", "role": "Request body validation", ...}`)
   - Improvement: Update the role text to reflect that pydantic is retained for `platform_contracts.Dataset`/`DatasetMeta`/`ColumnSchema` response-model construction (all defined as `BaseModel` in `02_Platform/packages/platform_contracts/contracts.py`), not for request body validation — the only endpoint that previously used Pydantic for request validation (`POST .../review`) now validates the raw body manually per this correction round.
   - Why: The dependency entry is still accurate (pydantic is genuinely required), but its stated purpose no longer matches actual usage after the `ReviewRequest` model was removed; left as-is it could mislead an implementer into thinking some other endpoint still uses Pydantic for request parsing.

2. **No test scenario for duplicate `anchor_slug` rejection** (carried forward, unresolved)
   - Location: `10_architecture.json` §contracts.failure_modes ("the same anchor_slug appears twice in one file"); `10_test_spec.md` §Scenarios; `10_scaffolding.json` §`tests/test_ingest.py`
   - Improvement: Add a scenario (and corresponding scaffolded test function) mirroring `test_ingest_duplicate_card_key_rejected` but for a duplicated `anchor_slug` across two sections in one file.
   - Why: Still one of eight explicitly declared ingestion failure modes with no corresponding test scenario or scaffolded test function; the correction round explicitly left this untouched (`12_design_corrections.md` §Unchanged by Design), consistent with it being outside the round-1 Minimal Change Set.

## Scaffold-Only Observations
1. **`tests/fixtures.sql` role description does not name the specific fixture ids the test spec relies on** (carried forward, unresolved)
   - Location: `10_scaffolding.json` §`tests/fixtures.sql`
   - Observation: `10_test_spec.md` references specific fixture flashcards by id (`fc-origins-1`, `fc-origins-2`, `fc-origins-3`, `fc-not-due`); the scaffold's `fixtures.sql` role text still only describes required states, not these ids.
   - Impact on implementation: Low risk of the test-writer choosing different fixture ids than the ones named in the scenarios, weakening given/when/then traceability. Unchanged since round 1.

## Hard Rule Violations
None identified.

## Open Uncertainties
1. **No explicit ColumnSchema for the essay-detail Dataset's nested `sections` field** (carried forward, unresolved)
   - Location: `10_architecture.json` §internal_flow step 5 (`essay_detail`); `10_scaffolding.json` §`backend/routers/essays.py` (`ESSAY_SCHEMA` documented only for id/title/slug)
   - Uncertainty: `ColumnType` in the UI Data Contract has no array/object type, so a nested `sections` list has no directly expressible `ColumnSchema` entry. Round 1 left this to the implementer (StorageTracker `history`-field precedent); the correction round did not touch it, consistent with it being outside the Minimal Change Set.
   - Why it matters: Left unresolved, an implementer could diverge from the StorageTracker precedent for how nested detail data is carried on a Dataset row.
   - Suggested owner: Implementer.

## Minimal Change Set
None — no required changes remain.

## Approval Condition
- None — approved as-is.
