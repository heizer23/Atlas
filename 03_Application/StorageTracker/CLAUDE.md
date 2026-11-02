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

## Kitchen extension (stock ledger)
- items: `quantity` numeric, `unit`, `expires_at`, `kind` (ingredient|batch), `recipe_ref` (opaque Kitchen recipe id).
- `stock_movements` ledger: quantity = cached sum of applied deltas; delta clamped so quantity never < 0
  (`requested_delta` keeps the ask). `POST /api/items/{id}/movements` is idempotent via `idempotency_key`;
  `POST /api/movements/{id}/reverse` once per movement. Absolute PATCH of quantity writes a `patch` correction movement.
- `kind='batch'` skips the low-stock auto transition and shopping tasks.
- Known pre-existing failures: test_list_items_no_filter / test_list_items_state_filter (fixtures.sql grew to 20 items in Sprint 2).
