# Test Spec — StorageTracker — Sprint01_Core

## Scope

Backend API tests using pytest + httpx ASGI transport. Tests run against the FastAPI app with a test Postgres database (requires DATABASE_URL or ATLAS_PG_* env vars pointing to a test DB).

Frontend is covered by manual smoke testing in Sprint 1 (no frontend test framework configured).

## Test file locations

- `03_Application/StorageTracker/tests/conftest.py` — fixtures (app client, schema setup/teardown)
- `03_Application/StorageTracker/tests/test_items.py` — item CRUD and view endpoint tests

## Required env

`DATABASE_URL=postgresql://atlas:password@localhost:5432/atlas_test` or equivalent ATLAS_PG_* vars.

## Test cases

### TC-001: Create item — minimal (object type)
- POST /api/items with {name, item_type=object}
- Expect 200, Dataset with 1 row, state=stored, source_tags=[]

### TC-002: Create item — consumable with quantity auto-transition
- POST /api/items with {name, item_type=consumable, quantity=2, min_quantity=5}
- Expect state=low_stock (auto-transition applied, quantity <= min_quantity)

### TC-003: Create item — consumable, caller sets state explicitly
- POST /api/items with {name, item_type=consumable, quantity=2, min_quantity=5, state=missing}
- Expect state=missing (caller-supplied state wins over auto-transition)

### TC-004: List items — no filter
- POST two items, GET /api/items
- Expect Dataset with both items, ordered by created_at DESC

### TC-005: List items — filter by state
- Create items with different states, GET /api/items?state=low_stock
- Expect only low_stock items returned

### TC-006: List items — filter by source_tag
- Create consumable with source_tags=["Rewe", "DM"], GET /api/items?source_tag=Rewe
- Expect item returned

### TC-007: List items — invalid state filter
- GET /api/items?state=invalid_state
- Expect 400 ApiError with code INVALID_FILTER

### TC-008: Get single item with history
- Create item, PATCH to change state, GET /api/items/{id}
- Expect Dataset 1 row with embedded history list; history has 2 entries (created + state_change)

### TC-009: Patch item — state change records history
- Create item (state=stored), PATCH state=missing
- GET /api/items/{id}/history — expect 2 entries: created, state_change

### TC-010: Patch item — auto-transition on quantity update
- Create consumable {quantity=10, min_quantity=5} — state=stored
- PATCH {quantity=3} — expect state auto-transitions to low_stock
- History includes quantity_change and state_change entries

### TC-011: Patch item — caller state wins over auto-transition
- Create consumable {quantity=10, min_quantity=5}
- PATCH {quantity=3, state=out_of_stock} — expect state=out_of_stock (not low_stock)

### TC-012: Patch item — field omission does not clear
- Create item with location="kitchen"
- PATCH {state=missing} — GET item — location still "kitchen"

### TC-013: Patch item — explicit null clears nullable field
- Create item with location="kitchen"
- PATCH {location=null} — GET item — location is null

### TC-014: Patch item — source_tags null rejected
- PATCH {source_tags: null} — expect 400 VALIDATION_ERROR

### TC-015: Delete item
- Create item, DELETE /api/items/{id}
- Expect empty Dataset; subsequent GET returns 404

### TC-016: Delete cascades to history
- Create item, trigger history entries, DELETE item
- item_history rows for that item_id should be gone (verify via direct DB query or confirm 404 on history endpoint)

### TC-017: View low_stock
- Create: consumable low_stock, consumable out_of_stock, object stored
- GET /api/items/views/low_stock — expect 2 items (consumable ones), ordered by name ASC

### TC-018: View recycling
- Create item with state=marked_for_recycling, GET /api/items/views/recycling
- Expect that item returned

### TC-019: View important
- Create object and consumable, GET /api/items/views/important
- Expect only the object returned

### TC-020: View search — substring match
- Create item with name="old printer", GET /api/items/views/search?q=printer
- Expect item returned

### TC-021: View search — empty q returns empty Dataset
- GET /api/items/views/search (no q param, or q="")
- Expect Dataset with 0 rows

### TC-022: Route ordering — views not captured as {id}
- GET /api/items/views/low_stock should return Dataset, not a 404/422 from treating "views" as item ID

### TC-023: History endpoint — full history
- Create item, PATCH state, PATCH location, PATCH quantity
- GET /api/items/{id}/history — expect 4 entries (created + 3 changes) ordered by timestamp DESC

### TC-024: Not found — PATCH unknown ID
- PATCH /api/items/00000000-0000-0000-0000-000000000000 — expect 404

### TC-025: Not found — DELETE unknown ID
- DELETE /api/items/00000000-0000-0000-0000-000000000000 — expect 404

### TC-026: Validation — empty name rejected
- POST /api/items {name="", item_type=object} — expect 400 VALIDATION_ERROR

### TC-027: Validation — negative quantity rejected
- POST /api/items {name=x, item_type=consumable, quantity=-1} — expect 400 VALIDATION_ERROR
