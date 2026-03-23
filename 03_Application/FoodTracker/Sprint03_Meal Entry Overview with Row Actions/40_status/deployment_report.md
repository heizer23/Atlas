# Deployment Report — FoodTracker Sprint03_Meal Entry Overview with Row Actions

## Deployed

Backend endpoints (`GET/PUT/DELETE /api/food/entries`, `GET /api/food/entries/{id}`, `POST /api/food/entries/{id}/copy`) and frontend pages (`EntriesPage`, `EntryDetailPage`) for meal entry overview with row-level delete, copy, and edit actions.

---

## Bugs Found During Human Review

### Bug 1 — `"detail"` rejected as invalid RowAction

**Symptom:** `GET /api/food/entries` returned HTTP 500. Page showed blank with nav disappearing on navigation.

**Root Cause Layer:** Platform contracts

**What happened:** The designer declared `row_actions: ["delete", "copy", "detail"]` in `architecture.json`. This is valid per the UI Data Contract (`07_UI_Data_Contract.md`), which defines `RowAction = string`. However, the Python platform implementation (`platform_contracts/contracts.py`) defines `RowAction = Literal["delete", "edit", "copy"]` — a closed enum that excludes `"detail"`. Pydantic rejected the value at runtime with a `ValidationError`.

**Contract violated:** `03_contracts_and_boundaries.md` — the Python implementation is more restrictive than the contract document specifies. The two are inconsistent.

**Fix applied:** Changed `"detail"` → `"edit"` in `entries.py` (two occurrences in `list_entries` and `update_entry`).

**Underlying fix still needed:** `platform_contracts/contracts.py` and `07_UI_Data_Contract.md` disagree on whether `RowAction` is open (`string`) or closed (`Literal`). This inconsistency will produce the same class of bug in any future sprint that uses a row action not in the Python enum.

---

### Bug 2 — Render crash when API returns non-Dataset response

**Symptom:** When the backend returned `{"detail": "Not Found"}` (FastAPI's default 404 shape), `isApiError` returned `false` (no `"error"` key), the response was cast to a Dataset, `dataset.rows` was `undefined`, and `entries.length` threw a `TypeError` during render — crashing through `ShellLayout` and removing the nav.

**Root Cause Layer:** Implementation

**What happened:** `EntriesPage.tsx` did not guard against `dataset.rows` being `undefined` after an API cast. Any backend response that is not an ApiError-shaped object and not a proper Dataset (e.g., a FastAPI default 404) falls through as a "successful" response with a broken shape.

**Fix applied:** `setEntries(dataset.rows ?? [])` in `EntriesPage.tsx`.

---

## Process Analysis

| Bug | Should have been caught at | Why it wasn't |
|---|---|---|
| `"detail"` not in Python enum | Platform contracts layer — before any sprint | The contract document says `string`; the Python implementation says `Literal`. Agents read the contract document. The deviation in the Python package is not visible from the contract. |
| Missing `?? []` guard | Implementation | Implementer did not add defensive coding for non-conformant API responses. |

Bug 1 is **not a design review failure** — the design was correct per the contract document. The design reviewer had no signal to catch it. The failure is a pre-existing inconsistency between the contract document and the platform implementation.

Bug 2 is a minor implementation robustness gap. It surfaced only because Bug 1 caused the backend to return an unexpected shape.

---

## Agent Improvement Recommendations

### designer-application / designer-platform
No change needed. Both agents correctly read the contract document. The design was valid per the contract.

### design-reviewer
No change needed for this class of bug. The reviewer correctly applied the contract. Adding an explicit "check RowAction enum values" rule would be wrong — it would couple the reviewer to the Python implementation detail rather than the contract.

### implementer
Add a defensive coding check: when casting an API response to a typed shape and accessing fields on it, guard against `undefined` — especially for array fields accessed with `.length` or `.map`.

### sprint-orchestrator / overall process
No structural change needed.

---

## Contract / Platform Gaps to Address

### RowAction inconsistency (priority: high)

**File:** `02_Platform/packages/platform_contracts/contracts.py`
**Issue:** `RowAction = Literal["delete", "edit", "copy"]` contradicts `07_UI_Data_Contract.md` which declares `RowAction = string`.
**Decision needed:** Should `RowAction` be open (any string) or closed (fixed enum)?
- If **closed**: update `07_UI_Data_Contract.md` to enumerate valid values, add the same list to the TypeScript types in `02_Platform/UI/react/src/api/types.ts`, and keep the Python `Literal`.
- If **open**: change the Python type from `Literal` to `str` to match the contract document.

Until this is resolved, any sprint using a row action outside `["delete", "edit", "copy"]` will hit a runtime Pydantic rejection with no design-time warning.
