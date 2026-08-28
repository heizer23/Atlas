# Design Corrections — EssayCards

## Applied Changes

1. **POST /review does not guarantee ApiError on all invalid-body shapes (Major)**
   - Review Source: `11_design_review.md` — Confirmed Problems #1, Minimal Change Set #1
   - Files Updated: `10_architecture.json`, `10_scaffolding.json`
   - Change: Removed reliance on Pydantic's automatic required-field enforcement for the `grade` body field on `POST /api/essaycards/flashcards/{flashcard_id}/review`. The design now specifies that the handler reads the raw JSON request body directly and validates `grade` manually (present, string, one of `{again, hard, good, easy}`) — so a missing `grade` key, a non-string value, an unparsable JSON body, or an out-of-set value are all caught by application code and returned as `ApiError` with `error.code="VALIDATION_ERROR"` (400), never FastAPI's default `RequestValidationError` 422 shape.
     - `10_architecture.json`: updated `interfaces.exposed_surfaces` (POST /review `body` field), `internal_flow` step 7 description, `contracts.invariants` (new invariant added, "four grade values" invariant left intact), `contracts.failure_modes` (VALIDATION_ERROR entry expanded), and the `deferrals.application_implementer` bullet for `backend/routers/flashcards.py`.
     - `10_scaffolding.json`: removed the `ReviewRequest` Pydantic `BaseModel` public object from `backend/routers/flashcards.py` (its presence would have re-introduced the bug, since a required `str` field on a Pydantic model still triggers `RequestValidationError` when omitted or wrong-typed); updated the file's `role` description to state the raw-body/manual-validation approach; added a private helper stub `_parse_review_grade` reflecting where this validation now lives.

2. **R-CON-BP-07 — Canonical Artifact Path (Hard Rule Violation)**
   - Review Source: `11_design_review.md` — Hard Rule Violations #1, Minimal Change Set #2
   - Files Updated: `10_architecture.json`
   - Change: Corrected `interfaces.consumes` from the non-existent `"platform_errorhandling from 02_Platform/03_ErrorHandling/"` to `"platform_errorhandling from 02_Platform/packages/platform_errorhandling/"`, matching the path already used in `dependencies.internal_required` and every existing Atlas consumer of this package.

## Unchanged by Design
- `10_schema.sql`: not touched — the fix is API-layer request validation only; no persisted-state or DDL change is implied.
- `10_test_spec.md`: not touched — it is not part of the Minimal Change Set. (The review's Recommended Improvement about a missing duplicate-`anchor_slug` test scenario and its own note about the review scenario coverage gap were both explicitly outside the Minimal Change Set and were not applied.)
- All other sections of `10_architecture.json` and `10_scaffolding.json` (data model, ingestion grammar, scheduling formula, GET endpoint definitions, UI deferrals, risks, deferred_decisions) are preserved verbatim.

## Review Alignment Check
- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — both Minimal Change Set items are applied in `10_architecture.json`; because the validation-error handling approach changed the scaffold's `ReviewRequest`/router shape, `10_scaffolding.json` was updated accordingly, per the review's own approval condition clause.
- Notes: The review offered two implementation options for fixing the Major issue (a scoped `RequestValidationError` exception handler, or manual raw-body validation as the sole source of truth). No existing Atlas component (`StorageTracker`, `Calendar`, `TaskTracker`, `WorkoutTracker`, `FoodTracker`, `NumericSeries`, `Chronicle`) installs a `RequestValidationError` handler or avoids Pydantic body models for mutation endpoints — there is no prior "proven pattern" in the codebase for either option (Calendar's `POST /events` uses a `BaseModel` and would have the same latent gap). The manual raw-body validation option was chosen as the smaller, more localized change, and because the original design already used the "plain `str`, validate in handler" philosophy for the out-of-set case — this extends that same approach to cover missing/wrong-type cases rather than introducing a new app-wide exception-handling mechanism. Re-review should confirm this resolution is acceptable.
