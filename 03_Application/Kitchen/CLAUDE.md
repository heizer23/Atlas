# CLAUDE.md

App-local guidance only. Global rules: repository root CLAUDE.md.

## App
Kitchen: weekly meal planner. Recipes -> week plan -> shopping list -> cook (backflush) -> eat.
Vision and scope: `Sprint01_Core/00_draft.md`.

## Boundaries
- Stock lives ONLY in StorageTracker (single source of truth). Kitchen reads/writes it through the HTTP
  contract (`backend/storage_client.py`): items (`kind` ingredient|batch, `unit`, `expires_at`, `recipe_ref`)
  and the ledger (`POST /items/{id}/movements`, `POST /movements/{id}/reverse`). Never query the storagetracker schema.
- Kitchen owns: recipes, plans, planned meals, cook/consumption events, `meal_bookings` (movement ids for undo).
- Three objects: Recipe (definition) -> cook_event + batch item (concrete run, stock) -> consumption_event.

## Booking contract
- Movement keys: `<cook|eat>:<meal_id>:<revision>:<line>`; repeating a request replays, never double-books.
- `planned_meals.revision` is bumped by undo so a re-confirmation books fresh.
- Moving, swapping, skipping a meal is a plan edit only: no movement.
- Cooking undo is refused while the batch is partly consumed (undo the eaten meals first).
- Eating more base portions than in stock: books what exists, reports `shortfall` (stock never goes < 0).
- Ingredient match in StorageTracker: name (case-insensitive) + unit; missing items are auto-created with quantity 0.

## Ports / schema
Host port 8028 (127.0.0.1) -> container 8000. Schema `kitchen`, from `schema.sql` at startup (idempotent).
Recipes are seeded at startup by name (`backend/seed.py`).

## Tests
`atlas-kitchen-test` (compose.yml in this folder). Needs a StorageTracker instance on `atlas_test`:
```
docker exec -d atlas-storagetracker-test uvicorn backend.main:app --host 0.0.0.0 --port 8000
make -C 01_System test-run COMPONENT=kitchen
```
Tests truncate `kitchen.*` and `storagetracker.items` in atlas_test. Rebuild the test container after code changes.

## Out of scope (Sprint 1)
Consumption statistics, nutrition optimisation, learning preferences, shelf-life forecasting, Foodtracker booking on eat
(the data model allows it later via the consumption_event).
