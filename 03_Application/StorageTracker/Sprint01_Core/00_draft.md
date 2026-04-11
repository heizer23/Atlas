# Sprint 01 — StorageTracker Core

## Goal

Build the foundational household item tracking application. The user can create and maintain items, see their current state and location, identify low-stock consumables, identify recycling candidates, and search for important stored objects.

## Component

- Name: StorageTracker
- Layer: 03_Application
- New component — no existing baseline

## Tech stack

Follow the same pattern as TaskTracker in this repo: FastAPI backend + PostgreSQL + React frontend registered with Atlas Shell. Use SQLAlchemy for ORM, Alembic for migrations, pytest for backend tests.

## Core domain concept

The central object is an **Item**. Every item has:
- `name` — what it is (e.g. "milk", "friend's key", "old printer")
- `item_type` — category: `consumable` | `object` | `pending_action`
- `state` — current lifecycle state (see below)
- `location` — free-text label of where it currently is (e.g. "kitchen cabinet", "hallway drawer")
- `notes` — optional free text
- `source_tags` — list of strings where it can be bought (e.g. ["Rewe", "DM"]); only meaningful for consumables
- `quantity` — approximate current quantity as integer; only for consumables (null for objects)
- `min_quantity` — threshold below which the item is considered low; only for consumables (null if not tracked)

## Item states

Use an enum. Allowed values:
- `stored` — present and accounted for (default)
- `low_stock` — consumable is running low (quantity <= min_quantity)
- `out_of_stock` — consumable fully depleted
- `marked_for_recycling` — item should leave the house
- `missing` — item cannot be found
- `lent_out` — item is with someone else

The `low_stock` state should be derived automatically: whenever quantity and min_quantity are both set and quantity <= min_quantity, the state should reflect this. The user can also manually set state to `low_stock` or `out_of_stock` for items without quantity tracking.

## History

Whenever an item changes state or location, record a history entry. Minimum fields:
- `item_id`
- `timestamp`
- `change_type` — `state_change` | `location_change` | `quantity_change` | `created`
- `old_value` — previous value as string
- `new_value` — new value as string
- `notes` — optional

## API endpoints

Backend must expose:

**Items**
- `GET /items` — list all items; support query params: `state`, `item_type`, `location`, `source_tag`
- `POST /items` — create item
- `GET /items/{id}` — get single item with recent history
- `PATCH /items/{id}` — partial update (state, location, quantity, notes, name)
- `DELETE /items/{id}` — delete item

**History**
- `GET /items/{id}/history` — full history for item

**Derived views (read endpoints, must return Dataset)**
- `GET /items/views/low_stock` — items where state is low_stock or out_of_stock
- `GET /items/views/recycling` — items where state is marked_for_recycling
- `GET /items/views/important` — items where item_type is object
- `GET /items/views/search?q=<text>` — search by name, location, notes

## UI views

Register with Atlas Shell as "StorageTracker". Provide these views:
1. **All Items** — filterable list of all items; chips for state/type filter
2. **Low Stock** — consumables that are low or out of stock
3. **Important Items** — objects (keys, documents, tools) — focus on location
4. **Recycling** — items marked for recycling
5. **Item Detail** — name, state badge, location, quantity (if consumable), source tags, history timeline

Item creation and editing should be possible inline (modal or inline form).

## Out of scope for this sprint

- Shopping tasks (Sprint 2)
- Notifications (Sprint 3)
- Location hierarchies (just free-text label)
- Barcode scanning
- Multi-user

## Open questions for designer to resolve

- Should `low_stock` auto-transition happen in the backend on every write, or be a computed field returned in the read response? Prefer: auto-update state on every PATCH that changes quantity.
- Should history be bounded (e.g. last 50 entries per item) or unbounded? Prefer: unbounded in DB, return last 20 in the item detail endpoint.
- Should source_tags be a simple array of strings or a separate table? Prefer: stored as a JSON array on the item row for MVP simplicity.
