# Architecture Audit — FoodTracker — 2026-04-14

**Verdict:** APPROVED_WITH_CHANGES (one fix applied inline)
**Date:** 2026-04-14
**Reviewer:** sprint_implement_reviewer (via Explore agent)

---

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change | Status |
|---|----------|--------------------------|-----------------|--------|
| 1 | `src/ShellEntry.tsx` lines 47, 63 — `PreviewData.quantity_g` and `PREVIEW_FIELDS` | R-CON-BP-04, R-CON-BP-09 — frontend type decoupled from backend field name | Rename `quantity_g` → `base_quantity`; update label to "Base Quantity (g)" | **FIXED** |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `entries.py` lines 242-244 — `_check_optional_nonneg` | PUT endpoint treats field omission and explicit null identically (both → 0.0); R-CON-AL-04 technically satisfied since this is documented behavior, but a clarifying comment would prevent future ambiguity |
| 2 | `entries.py` line ~347 — `GET /api/food/entries` docstring | No docstring; query behavior (no params, logged_at DESC, returns all rows) should be documented for R-CON-AL-01 completeness |
| 3 | Auth | No authentication on any endpoint; acceptable for current single-user local scope — revisit if deployment scope changes |

## Approval Condition

Blocking issue #1 was fixed inline (ShellEntry.tsx `quantity_g` → `base_quantity`). ARCHITECTURE_EXCEPTIONS.md already documented `base_quantity` correctly (no change needed). All other checks pass.

---

## Full Compliance Matrix

| Rule | Status | Notes |
|---|---|---|
| R-CON-BP-01 | PASS | Clear structure, explicit exceptions register |
| R-CON-BP-02 | PASS | UI Data Contract honored; schema boundary clean |
| R-CON-BP-03 | PASS | `foodtracker` schema owned; migrations 001-006 complete |
| R-CON-BP-04 | PASS (after fix) | All non-Dataset deviations registered in ARCHITECTURE_EXCEPTIONS.md |
| R-CON-BP-06 | PASS | AppRegistry consumer pattern matches Atlas Shell |
| R-CON-BP-07 | PASS | Canonical paths consistent across artifacts |
| R-CON-BP-08 | PASS | ARCHITECTURE_EXCEPTIONS.md entries self-contained |
| R-CON-BP-09 | PASS (after fix) | Frontend type now consistent with backend field name |
| R-CON-BP-10 | PASS | All helpers receive required inputs |
| R-CON-BP-11 | PASS | Interface cases match internal flow branches |
| R-CON-AL-01 | PASS | All endpoints documented; report docstring thorough |
| R-CON-AL-02 | PASS | All scope+mode combos handled in report endpoint |
| R-CON-AL-03 | PASS | All invariants realizable from declared inputs |
| R-CON-AL-04 | PASS | PATCH standard field required; PUT semantics consistent if undocumented |
| R-CON-AL-05 | PASS | Round-trip complete for all editable fields |
| R-CON-AL-06 | PASS | Client time for logged_at; server time for report/copy — both declared |

---

## Summary

FoodTracker is architecturally mature. Schema ownership is clean, API contracts are well-managed through the exceptions register, test coverage is comprehensive (Sprint06 + Sprint07 suites), and time authority is explicitly declared. The one blocking finding — a stale `quantity_g` field name in the frontend preview type — was a post-Sprint07 drift between backend and frontend types and has been corrected.
