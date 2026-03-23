# Design Review — food_tracker (Sprint 03: Meal Entry Overview with Row Actions)

## Verdict
- Status: APPROVED
- Summary: The corrected design addresses all three Minimal Change Set items from the first review round. The cross-module import violation is eliminated — entries.py is now a fully independent module. The `entry_detail` response shape is declared as an explicit named stable contract (`EntryDetail`). The items reconstruction product decision has been resolved by the human (Option A, 2026-03-21) and is recorded in `open_questions` as RESOLVED with an explicit `EntryEditRequest` named contract. The two Recommended Improvements (row_actions in exposed_surfaces, single-statement DELETE) are also applied. No confirmed problems remain. The design is approved for implementation.

---

## Round 1 Resolution Status

1. **`_validate_and_normalise` private/cross-module import** — RESOLVED
   - Resolution: Eliminated entirely. Option A removes the need for the import. entries.py uses its own private `_validate_entry_edit_request` validator. entries.py imports nothing from food.py or report.py.
   - Verification: `scaffolding.json` entries.py role states "Does NOT import from food.py". food.py `sprint03_changes` is empty. food.py `_validate_and_normalise.purpose` clarifies "Private to food.py — not exported, not imported by entries.py."

2. **`entry_detail` response shape not declared as explicit stable contract** — RESOLVED
   - Resolution: Promoted to `architecture.json contracts.named_contracts.EntryDetail`. Explicit fields, types, serialisation rules, and version declared. `interfaces.exposed_surfaces` for GET /entries/{id} and POST /entries/{id}/copy now carry `response_contract_ref: "contracts.named_contracts.EntryDetail"`. Scaffolding `EntryDetail` TypeScript type and `_serialise_entry_detail` now reference the named contract.
   - Verification: The named contract is the authoritative source; the scaffolding references it rather than redefining the shape.

3. **Items reconstruction product decision** — RESOLVED
   - Resolution: Human selected Option A (2026-03-21). `open_questions` entry added with status RESOLVED. `EntryEditRequest` named contract declared. PUT endpoint uses EntryEditRequest — no items field, no validate_and_normalise. dish_name is user-editable in the edit form.
   - Verification: `internal_flow[2]` (update_entry) confirms EntryEditRequest parsing. Invariant updated. `_buildPutBody` purpose reflects Option A body shape. `EntryDetailPage` purpose shows dish_name as user-editable.

---

## Confirmed Problems

None.

---

## Recommended Improvements

None remaining from Round 1. The following were applied during correction:
- row_actions declared in `interfaces.exposed_surfaces[0]` (GET /api/food/entries)
- DELETE single-statement approach specified in `internal_flow[3]`
- Datetime serialisation rules explicit in `contracts.named_contracts.EntryDetail.serialisation_rules`

---

## Minor Observations (Non-blocking)

1. **`classification.why_application` still mentions "reuse of the existing meal validation contract for edits"**
   - Location: `architecture.json` → `classification.why_application`
   - Observation: This sentence is now slightly stale — the edit path uses its own contract (EntryEditRequest), not the intake validation contract. The classification itself remains correct (entry management is still Application-layer domain logic). The prose is imprecise but not a rule violation. No change required for approval.
   - Suggestion: Future corrector pass could update this sentence to "the use of a domain-specific simplified edit contract (EntryEditRequest)" — but this is cosmetic only.

2. **`copy_entry` purpose in `scaffolding.json` still says "entry_detail dict" (not "EntryDetail")**
   - Location: `scaffolding.json` → `entries.py.copy_entry.purpose`
   - Observation: Uses lowercase "entry_detail dict" instead of referencing the named contract. Minor inconsistency with the corrected get_entry purpose and architecture contract references. Not a rule violation.
   - Suggestion: Future corrector pass could update to "EntryDetail dict (see architecture.json contracts.named_contracts.EntryDetail)".

---

## Hard Rule Violations

None.

---

## Open Uncertainties

None remaining. All open questions resolved.

---

## Approval Condition

Met. The design may proceed to implementation.

Required artifacts for the implementer:
- `00_input/draft.md` — sprint scope and acceptance criteria
- `20_design/architecture.json` — contracts, interfaces, internal_flow, deferrals (application_implementer, ui_implementer)
- `20_design/scaffolding.json` — file structure, object signatures, sprint03_changes
- `20_design/design_corrections.md` — correction rationale and Option A decision record

The implementer must read `deferrals.application_implementer` and `deferrals.ui_implementer` as their primary instruction set, cross-referenced against `internal_flow` steps 1–5 and `contracts.named_contracts.EntryDetail` / `contracts.named_contracts.EntryEditRequest`.
