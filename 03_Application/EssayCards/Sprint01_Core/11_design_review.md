# Design Review — EssayCards

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: This is a well-specified design. Both open design questions flagged in the draft (markdown ingestion grammar; deletion/reconciliation gap) were resolved with concrete, verifiable specificity rather than hand-waved. Layer placement, query-behavior explicitness, scope-mode closure, time authority, and cross-artifact table/key consistency all check out. Two Major issues must be corrected before implementation: a mutation-endpoint failure mode that bypasses the ApiError contract, and a stale/inconsistent dependency path within `10_architecture.json` itself.

## Confirmed Problems

1. **POST /review does not guarantee ApiError on all invalid-body shapes**
   - Severity: Major
   - Location: `10_architecture.json` §interfaces.exposed_surfaces (`POST /api/essaycards/flashcards/{flashcard_id}/review`) and `10_scaffolding.json` §`backend/routers/flashcards.py` (`ReviewRequest`)
   - Why it is a problem: The design deliberately makes `ReviewRequest.grade` a plain `str` (not `Literal`/enum) so an *out-of-set value* (e.g. `"maybe"`) can be caught in the handler and converted to `ApiError`. This only covers the case where `grade` is present and is a string. If `grade` is omitted entirely, or sent as a non-string JSON value (e.g. `123`, `null`), Pydantic raises `RequestValidationError` before the handler runs. The scaffold's only installed exception handler (`platform_errorhandling.logFastapi.install_exception_handlers`) catches the generic `Exception` type for 500s — it does not intercept `RequestValidationError` — so FastAPI's default 422 response (`{"detail": [...]}`) would be returned instead of the `ApiError` envelope (`{"error": {code, message, ...}}`).
   - Impact: Violates the mutation-endpoint contract in R-CON-BP-04 §9 ("Return `ApiError` on failure — never a bespoke error shape") for a reachable input (malformed/missing `grade`). `10_test_spec.md` only exercises the wrong-value case (`"grade": "maybe"`), so this gap would not be caught by the specified test suite either.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the design addressed the anticipated bad-value case but did not trace the full input-state space (missing field, wrong JSON type) against the actual validation pipeline (Pydantic-level vs. handler-level).

## Recommended Improvements

1. **No test scenario for duplicate `anchor_slug` rejection**
   - Location: `10_architecture.json` §contracts.failure_modes ("the same anchor_slug appears twice in one file"); `10_test_spec.md` §Scenarios; `10_scaffolding.json` §`tests/test_ingest.py`
   - Improvement: Add a scenario (and corresponding scaffolded test function) mirroring `test_ingest_duplicate_card_key_rejected` but for a duplicated `anchor_slug` across two sections in one file.
   - Why: This is one of eight explicitly declared ingestion failure modes but is the only one with no corresponding test scenario or scaffolded test function, leaving a documented invariant unverified.

## Scaffold-Only Observations

1. **`tests/fixtures.sql` role description does not name the specific fixture ids the test spec relies on**
   - Location: `10_scaffolding.json` §`tests/fixtures.sql`
   - Observation: `10_test_spec.md` references specific fixture flashcards by id (`fc-origins-1`, `fc-origins-2`, `fc-origins-3`, `fc-not-due`) to set up the "never reviewed", "repeat review", and "not yet due" scenarios. The scaffold's `fixtures.sql` role text only describes required *states* ("a due card", "a not-yet-due card", "a card with last_reviewed_at set") without naming these ids.
   - Impact on implementation: Low risk of the test-writer picking different fixture ids than the ones named in the scenarios, weakening the given/when/then traceability link the test spec is designed to provide.

## Hard Rule Violations

1. **R-CON-BP-07 — Canonical Artifact Path**
   - Rule Source: `.claude/rules/R-CON-BP.md`
   - Location: `10_architecture.json` §interfaces.consumes (`"platform_errorhandling from 02_Platform/03_ErrorHandling/"`) vs. §dependencies.internal_required (`"02_Platform/packages/platform_errorhandling"`)
   - Violation: The same dependency is referenced by two different paths within the same artifact. `02_Platform/03_ErrorHandling/` does not exist in the repository (confirmed by filesystem search); the real package lives at `02_Platform/packages/platform_errorhandling/`, which is exactly what `dependencies.internal_required` and every existing consumer (e.g. `StorageTracker/backend/main.py`: `from platform_errorhandling.logFastapi import install_exception_handlers`) actually use.
   - Required Fix: Correct §interfaces.consumes in `10_architecture.json` to read `"platform_errorhandling from 02_Platform/packages/platform_errorhandling/"`, matching the path already used in §dependencies.internal_required.

## Open Uncertainties

1. **No explicit ColumnSchema for the essay-detail Dataset's nested `sections` field**
   - Location: `10_architecture.json` §internal_flow step 5 (`essay_detail`); `10_scaffolding.json` §`backend/routers/essays.py` (`ESSAY_SCHEMA` is documented only for the list endpoint: id/title/slug)
   - Uncertainty: `ColumnType` in the UI Data Contract is a closed enum (`string`, `number`, `date`, `boolean`, `enum`) with no array/object type, so a formal `ColumnSchema` entry for a nested `sections` list is not directly expressible. The design does not state whether the detail endpoint needs its own schema constant (with `sections` simply left undeclared, consistent with the precedent in `StorageTracker/src/ShellEntry.tsx` where `item.history` is read directly off the row via `(item as any).history` without a matching schema entry) or some other resolution.
   - Why it matters: Left unresolved, an implementer could reasonably diverge from the StorageTracker precedent (e.g., invent a schema entry with an unsupported type, or a bespoke non-Dataset shape for this one endpoint), which would be inconsistent with how the rest of the codebase handles nested detail data within Dataset rows.
   - Suggested owner: Implementer (resolve by following the StorageTracker `history`-field precedent; no architecture change needed if that precedent is confirmed acceptable).

## Minimal Change Set
1. Add explicit handling so that any malformed or missing `grade` body field on `POST /api/essaycards/flashcards/{flashcard_id}/review` returns `ApiError` with `error.code="VALIDATION_ERROR"` — either via a `RequestValidationError` handler scoped to this app, or by making the handler-level validation the only source of truth (e.g., accept the raw body and validate manually rather than relying on Pydantic's required-field enforcement).
2. Correct `10_architecture.json` §interfaces.consumes to reference `02_Platform/packages/platform_errorhandling/` instead of the non-existent `02_Platform/03_ErrorHandling/`, matching §dependencies.internal_required.

## Approval Condition
- Both Minimal Change Set items are applied in `10_architecture.json` (and, if the validation-error handling approach changes the scaffold's `ReviewRequest`/router shape, in `10_scaffolding.json`), and re-review confirms `POST .../review` returns `ApiError` for every invalid-body case, not just out-of-set grade values.
