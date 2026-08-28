---
name: project_essaycards_sprint01
description: EssayCards Sprint01_Core — new application (essay reader + SRS flashcards); TESTS_PASSING; two design questions resolved in round 1, two Major fixes in one correction loop, full implement+test loop completed in one pass with zero fix iterations
metadata:
  type: project
---

EssayCards is a brand-new `03_Application` component: pairs long-form essay reading with
spaced-repetition flashcards linked back to the exact passage that taught them. Sprint01_Core
proves the mechanic end-to-end on a single essay (markdown ingestion → reader → review queue →
grading with a custom SRS formula). Component name kept as `EssayCards` (component_name
`essaycards`), container `atlas-essaycards`, host port **8024** (next free after StorageTracker
8022, Calendar 8023), API prefix `/api/essaycards`.

**Why:** the human draft explicitly flagged two open design questions and asked the designer to
resolve them concretely rather than leave them ambiguous — this shaped the design-agent prompt
significantly (had to name both questions explicitly in the launch prompt, otherwise a designer
could plausibly punt on them since the draft itself said "designer must finalize").

Design took one full review-correct-reapprove loop:
- Round 1 review (`11_design_review.md`) verdict `APPROVED_WITH_CHANGES` with two Major findings:
  1. R-CON-BP-04 gap — `POST /review`'s Pydantic `ReviewRequest` model let a missing/malformed
     `grade` field fall through to FastAPI's default `RequestValidationError` (raw 422), bypassing
     the `ApiError` envelope, because the installed exception handler only catches generic
     `Exception`, not `RequestValidationError`.
  2. R-CON-BP-07 — `10_architecture.json` §interfaces.consumes pointed at a stale/nonexistent path
     `02_Platform/03_ErrorHandling/` while §dependencies.internal_required correctly pointed at
     `02_Platform/packages/platform_errorhandling`.
- Corrector fix for #1 was notable: rather than patch the Pydantic model, it removed the
  `ReviewRequest` Pydantic model entirely and switched to manual raw-body validation in the
  handler — because *any* Pydantic body model (even with a plain `str` field) still triggers
  FastAPI's automatic `RequestValidationError` machinery on missing/malformed input. No existing
  Atlas component (checked StorageTracker, Calendar, TaskTracker, WorkoutTracker, FoodTracker,
  NumericSeries, Chronicle) had a working precedent for this — Calendar's own `POST /events` has
  the same latent gap, unfixed. This is a **recurring pattern worth watching**: any future mutation
  endpoint using a Pydantic body model in this codebase likely has the same
  R-CON-BP-04/ApiError-bypass gap unless it explicitly avoids Pydantic body validation.
- Round 2 review (`13_design_review.md`) verdict `APPROVED` — both fixes verified coherent, no
  new regressions from removing the Pydantic model.

**How to apply:** Per explicit user instruction for that earlier session, orchestration stopped at
`DESIGN_APPROVED` rather than auto-continuing to `sprint_implement` — user wanted to check in
before implementation starts. A later session explicitly asked to drive the loop forward
automatically instead, and it completed cleanly: `sprint_implement` built the full component
(backend, ingestion CLI, `atlas-essaycards` + `atlas-essaycards-test` containers, frontend,
all four shell-wiring files, `react-markdown` shell dependency) in one pass — no design gaps
required a second implementer round. `sprint_test_runner` then ran 36 tests (22 backend
scenarios from `10_test_spec.md` plus scheduling-formula and shell-proxy tests) against
`atlas-essaycards-test`, all passing, verdict `TESTS_PASSING`, `fix_iterations` stayed at 0.
Final state: `TESTS_PASSING`, `50_test_report.md` written. The 4 `[UI — manual]` scenarios from
`10_test_spec.md` are recorded as MANUAL (not failures, no `tests/ui/` dir expected) and need a
human to eyeball the Reader/Review Session views before `/sprint-close`. `/sprint-close` was
explicitly kept out of scope for the orchestration run and is still the next human action.

See also: general note that Atlas's exception-handler setup
(`platform_errorhandling.logFastapi.install_exception_handlers`) does not catch
`RequestValidationError` — only generic `Exception` — so any component with Pydantic-validated
request bodies should be checked for the same ApiError-bypass risk on future reviews. EssayCards'
own `POST .../review` endpoint avoided this by validating the raw body manually with no Pydantic
model — a real precedent to point future implementers at (repo's first working fix for this gap;
Calendar's `POST /events` still has the same latent issue, unfixed as of this writing).
