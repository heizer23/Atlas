---
name: FoodTracker Sprint07 Pattern
description: Column rename sprint (quantity_g → base_quantity); IMPLEMENTATION_IN_PROGRESS; container rebuild required before test run
type: project
---

Sprint07_Base_Quantity renames `quantity_g` to `base_quantity` across schema, migrations, backend, and frontend.

Key facts:
- Migration: `migrations/006_rename_quantity_g.sql` — backfills NULL→100, renames column, adds NOT NULL DEFAULT 100, replaces constraint
- schema.sql updated with base_quantity NOT NULL DEFAULT 100
- `food.py`, `entries.py` fully renamed
- `EntryDetailPage.tsx` fully renamed; perUnit state formula changed (÷base_quantity not ÷100 then ×100)
- ARCHITECTURE_EXCEPTIONS.md EXC-FT-03 updated (EntryDetail named contract)
- `tests/fixtures.sql` updated (base_quantity, no NULLs)
- `tests/test_sprint06.py` updated to use base_quantity assertions
- `tests/test_sprint07.py` written for all 8 backend scenarios

Current state: IMPLEMENTATION_IN_PROGRESS

**Why:** Container rebuild required before tests can run — Dockerfile COPYs source at build time; prod database needs migration 006 run before backend restart.

**How to apply:** Before running test runner, rebuild and restart containers:
```
docker compose -f 03_Application/FoodTracker/compose.yml build && docker compose -f 03_Application/FoodTracker/compose.yml up -d
```
Run migration 006 against prod database:
```
docker exec atlas-postgres psql -U atlas -d atlas -f /path/to/migrations/006_rename_quantity_g.sql
```
Then invoke sprint_test_runner or /sprint-close.
