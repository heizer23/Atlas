# Sprint 02 — StorageTracker Shopping Tasks

## Goal

Turn shopping-relevant item states into actionable tasks. Low-stock items can create or maintain shopping tasks. Tasks carry source context (Rewe, DM, Amazon). Completing a task resolves the action loop back in the item.

## Component

- Name: StorageTracker
- Layer: 03_Application
- Existing component — Sprint 02 extends Sprint 01

## Design decisions from Sprint 01

- Items are the truth. Shopping tasks are derived from item state, not maintained separately.
- Item states `low_stock` and `out_of_stock` are the triggers for shopping task creation.
- Source tags (Rewe, DM, etc.) already live on items.

## Core concept for this sprint

Introduce a **ShoppingTask** object. A shopping task is:
- linked to exactly one item (`item_id`)
- has a status: `open` | `done` | `dismissed`
- carries the source tags from the item at task creation time (denormalized for query efficiency)
- has a `notes` field for any additional context
- has `created_at` and `completed_at` timestamps

**Key invariants:**
- An item can have at most one `open` shopping task at a time.
- When an item transitions to `low_stock` or `out_of_stock`, a shopping task should be created if one does not already exist.
- When a shopping task is marked `done`, the item's quantity should be updated:
  - If the item has quantity tracking: reset quantity to a sensible default (e.g. `min_quantity * 3` or a user-provided `restock_quantity`). If `restock_quantity` is not set on the item, just set state back to `stored`.
  - If the item has no quantity tracking: set state back to `stored`.
- When a shopping task is `dismissed`, nothing changes on the item state. The task is simply closed.

## New field on Item

Add `restock_quantity` (integer, nullable) to the Item model. This is the quantity to restore when a shopping task is completed. If null, just set state to `stored` on task completion.

## Auto-task creation

When a PATCH to an item results in state becoming `low_stock` or `out_of_stock`:
- check if an open shopping task exists for this item
- if not, create one automatically

This logic runs in the backend service layer.

## API endpoints

**Shopping Tasks**
- `GET /shopping-tasks` — list tasks; query params: `status` (default: `open`), `source_tag`
- `POST /shopping-tasks` — manually create a task for an item (useful for items that are not yet low but the user wants to note for next shop)
- `PATCH /shopping-tasks/{id}` — update status (done | dismissed); on `done`, triggers item state reset
- `DELETE /shopping-tasks/{id}` — delete task

**Derived views (must return Dataset)**
- `GET /shopping-tasks/views/by_source` — tasks grouped by source_tag; useful for "what do I need at Rewe?"

## UI additions

- New view: **Shopping List** — open tasks, grouped optionally by source tag
- Items in low_stock or out_of_stock state in All Items view should show a shopping-task indicator (e.g. a small badge)
- From Item Detail, user can manually trigger "Create shopping task"
- Task completion UI should be available from the Shopping List view (one-tap done/dismiss)

## Out of scope

- Notifications (Sprint 3)
- Recurring tasks / auto-reorder schedules
- Multi-store route optimization
- Budget tracking

## Open questions for designer to resolve

- Should auto-task creation be synchronous in the PATCH endpoint handler or triggered asynchronously? Prefer: synchronous, in the service layer.
- Should `by_source` view return items with no source tag in an "Other" group or exclude them? Prefer: include them in an "Other" group.
- If an item has multiple source tags (e.g. ["Rewe", "Amazon"]), which tag drives grouping? Prefer: item appears in each group it belongs to (duplicated across groups in the view).
