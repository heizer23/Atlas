# Design Corrections — Sprint 03: Meal Entry Overview with Row Actions

## Correction Round
- Round: 1
- Date: 2026-03-21
- Corrector: design-corrector
- Input: `20_design/design_review.md` — verdict CHANGES_REQUIRED (3 Minimal Change Set items)
- Human product decision: Option A selected 2026-03-21 (items reconstruction open question resolved)

---

## Item 1 — Resolved: `_validate_and_normalise` private/cross-module import violation

**Design review finding:** Confirmed Problem #1 (Critical). `_validate_and_normalise` declared private in food.py but instructed to be imported cross-module by entries.py, violating Atlas Rule 03 contracts_and_boundaries.

**Resolution applied:** Option A resolution from the product decision supersedes this violation entirely. Because the human selected Option A (simplified edit contract — no `_validate_and_normalise` reuse for the edit path), entries.py no longer imports from food.py at all. The cross-module coupling is eliminated, not merely renamed.

**Changes made:**

`architecture.json`:
- `contracts.invariants`: Replaced "reuses the same _validate_and_normalise contract" with "uses the EntryEditRequest contract — a simplified edit path separate from the intake flow; it does not invoke validate_and_normalise"
- `interfaces.exposed_surfaces[2]` (PUT): Updated purpose to reference EntryEditRequest contract. Added `request_contract_ref`.
- `deferrals.application_implementer`: Replaced the _validate_and_normalise import instruction with EntryEditRequest inline validation. Added explicit "entries.py must not import anything from food.py or report.py."
- `internal_flow[2]` (update_entry): Replaced "_validate_and_normalise(body)" flow with "_validate_entry_edit_request(body)" and EntryEditRequest field set.
- `failure_modes`: Updated VALIDATION_ERROR to reference EntryEditRequest validation, not _validate_and_normalise.
- `deferrals.reviewer`: Added "Confirm entries.py imports nothing from food.py or report.py" and "Confirm PUT endpoint parses EntryEditRequest body directly — does NOT call validate_and_normalise."

`scaffolding.json`:
- `entries.py.role`: Removed "Imports _validate_and_normalise from food.py" note. Updated to "Does NOT import from food.py."
- `entries.py.update_entry.purpose`: Updated to reference _validate_entry_edit_request and EntryEditRequest.
- `entries.py.private_objects`: Added `_validate_entry_edit_request` function declaration.
- `food.py.role`: Removed Sprint 03 cross-module import note.
- `food.py.sprint03_changes`: Set to empty array (food.py is genuinely unchanged).
- `food.py._validate_and_normalise.purpose`: Clarified "Private to food.py — not exported, not imported by entries.py."

---

## Item 2 — Resolved: `entry_detail` response shape promoted to named stable contract

**Design review finding:** Confirmed Problem #2 (Major). `entry_detail` response shape declared only in prose in `interfaces.exposed_surfaces` purpose field. Not an explicit stable contract artifact.

**Resolution applied:** Promoted to two named contracts in `architecture.json.contracts.named_contracts`:

**Changes made:**

`architecture.json`:
- Added `contracts.named_contracts.EntryDetail`: Explicit stable contract with all fields, types, serialisation rules, and version. Referenced by `GET /api/food/entries/{id}` and `POST /api/food/entries/{id}/copy` via `response_contract_ref`.
- Added `contracts.named_contracts.EntryEditRequest`: Explicit stable contract for PUT request body (Option A shape). Referenced by `PUT /api/food/entries/{id}` via `request_contract_ref`.
- `contracts.provides`: Updated "entry detail dict" references to "EntryDetail" (named contract).
- `interfaces.exposed_surfaces`: Updated `ui_contract` fields to reference named contracts. Added `response_contract_ref` and `request_contract_ref` fields.
- `deferrals.application_implementer`: Updated to reference "contracts.named_contracts.EntryDetail" and "contracts.named_contracts.EntryEditRequest" rather than inline prose descriptions.

`scaffolding.json`:
- `entries.py._serialise_entry_detail.purpose`: Updated to reference "EntryDetail dict (see architecture.json contracts.named_contracts.EntryDetail)".
- `EntryDetailPage.EntryDetail.purpose`: Updated to reference "architecture.json contracts.named_contracts.EntryDetail".
- `EntryDetailPage._buildPutBody.purpose`: Updated to reference "EntryEditRequest contract (see architecture.json contracts.named_contracts.EntryEditRequest)".

---

## Item 3 — Resolved: Items reconstruction limitation surfaced as explicit product decision (Option A selected)

**Design review finding:** Confirmed Problem #3 (Major). `_buildPutBody` documented items reconstruction as "[{name: dish_name}]" — a product-level decision made unilaterally by the designer without human input.

**Resolution applied:** Human selected Option A on 2026-03-21: PUT body accepts `dish_name` and `nutrition` directly; no `items` field; edit and intake are separate flows.

**Changes made:**

`architecture.json`:
- `open_questions`: Added entry with status RESOLVED documenting Option A selection with date and owner.
- `contracts.invariants`: Updated invariant from "reuses validate_and_normalise" to "uses EntryEditRequest contract — simplified edit path."
- Added new invariant: "dish_name in the edit flow is accepted directly from the user in the PUT body; this differs from the intake flow where dish_name is derived server-side from items[].name."
- `risks`: Replaced the items reconstruction risk with an explicit note about Option A.

`scaffolding.json`:
- `EntryDetailPage._buildPutBody.purpose`: Replaced items reconstruction prose with Option A body shape description.
- `EntryDetailPage.EntryDetailPage.purpose`: Updated edit form to show dish_name as "user-editable text field" (not read-only). Updated Save action to reference EntryEditRequest body with no items field.
- `EntryDetailPage.EntryFormState.purpose`: Updated dish_name description to "user-editable in the edit flow, sent directly in PUT body."

---

## Recommended Improvements Applied (from design_review.md)

### Improvement 1 — row_actions declared in architecture exposed_surfaces

Applied: `interfaces.exposed_surfaces[0]` (GET /api/food/entries) now has explicit `row_actions: ["delete", "copy", "detail"]` and `dataset_meta.row_actions` fields.

### Improvement 2 — DELETE single-statement approach

Applied: `internal_flow[3]` (delete_entry) updated to single-statement approach: execute DELETE, check cursor.rowcount == 0 for 404. Added to `deferrals.reviewer` checklist.

Recommended Improvement 3 (created_at/updated_at timezone serialisation) is now covered explicitly in `contracts.named_contracts.EntryDetail.serialisation_rules`.

---

## Artifact State After Corrections

| File | Status |
|------|--------|
| `20_design/architecture.json` | Corrected — named contracts added, Option A recorded, DELETE flow updated, row_actions explicit |
| `20_design/scaffolding.json` | Corrected — food.py cross-module import removed, EntryEditRequest shape propagated, _validate_entry_edit_request added |
| `20_design/design_review.md` | Unchanged — original review artifact preserved |
| `20_design/design_corrections.md` | This file |

---

## Design Corrector Assessment

All three Minimal Change Set items from `design_review.md` are resolved. The design is now ready for a second review pass. The key structural change is that Option A simplifies the architecture: entries.py is a fully independent module with no cross-module dependencies on food.py. This is cleaner than the original design and directly addresses the Rule 03 violation at root rather than by renaming the private function.

The `contracts.named_contracts` section in architecture.json is the new stable reference for the EntryDetail and EntryEditRequest shapes. Both the backend deferral instructions and the frontend scaffolding now reference these named contracts rather than prose descriptions.
