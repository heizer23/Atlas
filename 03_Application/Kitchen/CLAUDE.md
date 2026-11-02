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

## Ingredient identity (Sprint 1.1)
- StorageTracker items (`kind=ingredient`, `item_type=consumable`) are the article master; recipe lines store
  `recipe_ingredients.item_id` = the article number (single fortlaufende integer, opaque ref, no FK). `name` on a line is only a display label; the live article name wins.
- Line status: `base` | `matched` | `unit_mismatch` | `unknown_id` | `unresolved` (`backend/ingredients.py`).
  Units are never converted: line unit must equal the article's base unit (article without unit accepts any).
- `recipes.status`: `active` iff every line is base/matched, else `draft`. Recomputed on every save and at startup.
  Drafts are excluded from plan suggestion, add/swap meal (409), shopping (reported as `draft_recipes`), cook/eat (409).
- Imports/exports use `item_id` as integer; ChatGPT gets the full list as `existing_skus` in the example JSON.
- Unknown article ids are rejected on save (400); unit mismatches and unresolved lines save as draft.
- Import (`backend/recipe_import.py`, format `atlas.kitchen.recipe` v1): `POST /recipes/import/preview` is read-only
  (parse, validate, match ids, suggestions = exact/substring name lookup only). The UI saves via `POST /recipes`.
  Same name as an existing recipe => 409, never overwritten. Import and article creation make no stock movements.
- Articles are created only by explicit user action: `POST /ingredients` (stock 0; 409 if the name exists).
- `GET /ingredients` = master export (zero stock included, batches excluded); `GET /recipes/import-example`.
- `migrate_legacy_ingredients()` (seed.py, startup, idempotent): one-time assignment of article ids to pre-1.1 recipe
  lines (existing article by name+unit, else create with stock 0), then status recompute. Not used by imports.
- Purchase / stocktake endpoints take `item_id`, not names.

## Plan length
`POST /plans/suggest {week_start?, days (1-7, default 7), cook_sessions?}`. `week_start` is the first day (default today, Berlin);
the column name is historical. `cook_sessions` default: 1 for <= 4 days, else 2; cooking days are day 0/3/5 offsets that fall inside
the plan. One dinner per day. Leftover portions stay in stock for the next plan. UI remembers days/cooks in localStorage (default 3 days).
`GET /plans` lists newest-created first; the UI and shopping list use the newest plan.

## Expiry
- Batch `expires_at` = cook day + recipe `shelf_life_days` (last good day, Berlin calendar). Status is derived by
  StorageTracker on read (`expired` / `expiring_soon` = within 2 days), never stored; only for quantity > 0.
- Eating consumes the earliest-expiring non-expired batch first and NEVER auto-consumes expired ones: the shortfall
  response reports `expired_in_stock`. Expired batches are only removed by a user-confirmed discard
  (`POST /batches/{item_id}/discard` or the StorageTracker UI), which books an `expired` ledger movement
  (key `expired:<item>:<date>`, shared by both UIs, reversible).
- Plan suggestion tracks portion lots with expiry (stock + planned cooks) and only places a base meal on days the base is good.
  `expiry_warning` on a planned meal = its base is expired/expires before that day and no planned cook covers it.

## Ports / schema
Host port 8028 (127.0.0.1) -> container 8000. Schema `kitchen`, from `schema.sql` at startup (idempotent).
Recipes are NOT seeded at startup; `backend/seed.py` is test fixture data only (tests/conftest.py).

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
