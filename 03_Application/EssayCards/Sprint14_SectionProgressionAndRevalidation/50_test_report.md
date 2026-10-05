# Test Report — EssayCards — Sprint14_SectionProgressionAndRevalidation

**Verdict:** TESTS_PASSING
**Date:** 2026-10-05
**Fix iteration:** 0

## Results

| Scenario | Test | Type | Status | Failure reason |
|----------|------|------|--------|----------------|
| Oral import and pass rule (11 scenarios: 5/6 pass, 4/6 fail, four kinds, slug rules, scope validation, all-or-nothing batch, package scope section/essay/invalid params) | tests/test_oral_state.py (one test per scenario) | backend | PASS | — |
| Section state and unlocking (12 scenarios) | tests/test_progress.py (one test per scenario) | backend | PASS | — |
| Card maturity (Learned at 30d; new/locked states) | tests/test_progress.py::test_learned_starts_at_30_days, test_new_and_locked_states | backend | PASS | — |
| Essay state (8 scenarios: grey/yellow/green/zero-card/blue/violet/retake/highest) | tests/test_progress.py | backend | PASS | — |
| Failure cascade and revalidation flagging (6 scenarios) | tests/test_oral_state.py | backend | PASS | — |
| Revalidation (9 scenarios) | tests/test_revalidation.py | backend | PASS | — |
| Essay list drops Sprint12 fields and adds new ones | tests/test_essays.py::test_essay_list_and_detail_drop_sprint12_fields_and_add_new_ones | backend | PASS | — |
| Category-level counts preserved; open_count excludes locked/flagged; oral history newest first | tests/test_progress.py | backend | PASS | — |
| Migration (3 backfill scenarios) | tests/test_progress.py::test_backfill_* | backend | PASS | — |
| [UI] Overview (4 scenarios) | tests/ui/section_progress_overview.spec.ts | UI | PASS | — |
| [UI] Reader and oral import (4 scenarios) | tests/ui/section_progress_overview.spec.ts | UI | PASS | — |
| [UI] Revalidation session | tests/ui/revalidation_session.spec.ts | UI | PASS | — |
| [UI] Essay progress zone traffic-light buckets | tests/ui/review_stats.spec.ts | UI | PASS | — |

No scenarios MISSING; no `[UI — manual]` scenarios in the spec.

## Test output

```
Backend: docker exec atlas-essaycards-test pytest tests/ -v
================= 339 passed, 4 warnings in 105.37s (0:01:45) =================
(warnings: FastAPI on_event / httpx deprecation only; the known test_examinations date flake did not occur)

UI: docker exec atlas-playwright npx playwright test 03_Application/EssayCards/tests/ui/ ... --reporter=list
  25 passed (6.5s)
```

## Failure Analysis

All scenarios passed.

## Required Action

Proceed to /sprint-close.
