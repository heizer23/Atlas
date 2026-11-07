# CLAUDE.md

This file contains app-local guidance only.
Global architecture and development rules are defined in the repository root CLAUDE.md.

## App
StorageTracker is a household item tracking application. Users track consumables (with quantity), objects (with location), and pending_action items.

## Sprint scope
- Sprint 1: Core CRUD, item history, views (low_stock, recycling, important, search), React UI
- Sprint 2: Shopping tasks
- Sprint 3: Notifications and geofencing

## Pattern references
Follow the same patterns as TaskTracker (03_Application/TaskTracker):
- FastAPI backend, psycopg2 connection pool, RealDictCursor
- platform_contracts for Dataset responses
- platform_errorhandling for api_error and middleware
- Atlas Shell registration via src/shellConfig.ts

## Port
StorageTracker backend runs on host port 8022 (container port 8000).

## Schema
storagetracker schema in the shared Atlas Postgres instance.
Tables: storagetracker.items, storagetracker.item_history, storagetracker.shopping_tasks, storagetracker.stock_movements
Schema initialized idempotently at startup from schema.sql.

## Article number
`items.id` is a single fortlaufende integer (identity, never reused), shown as `#id` in the UI and used by Kitchen as
the article identity. Converted from uuid on 2026-11-02 (mapping table dropped afterwards). Test fixtures use 1000001+.

## Kitchen extension (stock ledger)
- items: `quantity` numeric, `unit`, `expires_at`, `kind` (ingredient|batch), `recipe_ref` (opaque Kitchen recipe id).
- `stock_movements` ledger: quantity = cached sum of applied deltas; delta clamped so quantity never < 0
  (`requested_delta` keeps the ask). `POST /api/items/{id}/movements` is idempotent via `idempotency_key`;
  `POST /api/movements/{id}/reverse` once per movement. Absolute PATCH of quantity writes a `patch` correction movement.
- `kind='batch'` skips the low-stock auto transition and shopping tasks.
- Known pre-existing failures: test_list_items_no_filter / test_list_items_state_filter (fixtures.sql grew to 20 items in Sprint 2).

## Expiry
`items.expires_at` (date, last good day). `expiry_status` is derived on read from the server date (Europe/Berlin):
`expired` (< today), `expiring_soon` (<= today + 2 days), only for quantity > 0. `GET /api/items/views/expiring` lists both,
earliest first. UI: banner on All Items, `/items/expiring` view, Discard button on expired items = `expired` ledger movement
(key `expired:<id>:<expires_at>`, confirmation dialog first, reversible). Nothing is removed automatically.

## Batch lifecycle
`items.produced_at` (cooking date), `items.archived_at` (depleted, out of active inventory; rows + history stay). Batches are archived
automatically when a movement brings them to 0 and reactivated by a reversal; `GET /items` hides archived by default (`archived=include|only`).
`POST /items/{id}/relocate {location, event: move|freeze|thaw, expires_at}` writes `freeze` / `thaw` / `location_change` plus `expiry_change`
history rows; freeze/thaw REQUIRE an explicit non-past `expires_at` (shelf life is never reset implicitly). `POST /items/{id}/archive|unarchive`.

## Stock management type & categories
- `items.stock_management_type` QUANTITY (default, ledger) | KANBAN. Kanban reuses `items.state` as the manual status
  (stored = In Stock, low_stock = Low, out_of_stock = Out); Low/Out create the open shopping task, task `done` resets to `stored` (no quantity touched).
  Movements on Kanban articles are recorded with `delta` 0 (`requested_delta` keeps the ask) so Kitchen idempotency/undo work; no quantity auto-transition.
  Kitchen `compute_shopping` skips Kanban articles. Batches cannot be Kanban.
- `items.category` (Vegetables & Fruit, Meat & Fish, Dairy, Dry Goods, Spices, Frozen, Beverages, Other; default Other). `GET /items?category=&stock_management_type=`.
  UI: category chips + grouped list on All Items; Kanban status chips on the card.
- "Copy as text" on the shopping list (flat or by store; clipboard, share sheet fallback).

## Central shopping list (single list, owned here)
- `GET /shopping-tasks/views/central` (Dataset) = one row per article that is short OR has an open task. `backend/purchasing.py`:
  usable stock = quantity (0 if past its best-before); gross demand = sum over all sources; shortage = max(0, demand - usable stock),
  stock subtracted once per article; purchase qty = shortage -> raised to `items.min_purchase_qty` -> rounded UP to a multiple of
  `items.purchase_multiple` (both nullable, base unit). KANBAN demand is ignored (status task covers it). Rows show `origins`:
  `kitchen` (demand), `manual` / `low_stock` (open `shopping_tasks.origin`).
- Demand = `storagetracker.demands` (source, external_ref, item_id, qty, unit, required_date, label), NOT a stock movement. Internal
  API `PUT /api/internal/demands/{source}` replaces one source's snapshot atomically (all-or-nothing; invalid item/unit/qty/batch/duplicate
  ref/malformed -> 422 with per-line problems, previous snapshot untouched, rejection stored in `demand_sync`); identical re-send is a no-op.
  `GET .../{source}` lines, `GET .../{source}/status`. Auth: `X-Atlas-Service-Token` = env `ATLAS_SERVICE_TOKEN` (unset -> 503, fail
  closed). The paths are not proxied by the shell nginx (only /api/items and /api/shopping-tasks are).
- `POST /shopping-tasks/purchase {item_id, qty, idempotency_key}` = "Bought": one `purchase` movement + closes the open task WITHOUT
  the restock reset. Demand rows then shrink/vanish by recalculation (never recreated). Task-only rows keep Done/Dismiss.
- `GET /shopping-tasks/views/demand_status` feeds the "update rejected" banner above the list.
