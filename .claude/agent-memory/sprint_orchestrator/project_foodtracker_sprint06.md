---
name: FoodTracker Sprint06 Pattern
description: Search/scale/averages sprint; IMPLEMENTATION_IN_PROGRESS; test container needs rebuild before tests can run
type: project
---

FoodTracker Sprint06_Search_Scale_Averages completed design and implementation. State: IMPLEMENTATION_IN_PROGRESS, awaiting test run.

**Why:** The `food-tracker-test` service was newly added to `compose.yml` in this sprint (did not previously exist). The test infrastructure (conftest.py, fixtures.sql, test_sprint06.py) was also created fresh. Container must be built before tests can run.

**How to apply:** Before invoking sprint_test_runner, operator must:
1. `docker compose -f 03_Application/FoodTracker/compose.yml build` — rebuilds image with schema.sql, tests/, pyproject.toml dev extras
2. `docker compose -f 03_Application/FoodTracker/compose.yml up -d food-tracker-test` — starts test container
3. `docker exec atlas-postgres psql -U atlas -c "CREATE DATABASE atlas_test;" 2>/dev/null || true`
4. Apply `03_Application/FoodTracker/migrations/005_add_quantity_g.sql` to production db
5. Rebuild Atlas Shell (ReportPage.tsx, EntriesPage.tsx, EntryDetailPage.tsx all changed)

Sprint features: (1) alcohol_g_total in all report scopes, (2) avg line extended to week/month, (3) client-side search on Entries tab, (4) quantity_g scaling on Log tab.

Key implementation notes:
- `schema.sql` was backfilled to include Sprint04 columns (standard, source_standard_id) which were missing before Sprint06
- test_alcohol_g_avg_cumulative_average_is_correct uses `scope=week` — fixture rows from 2026-04-10/11 fall within week window on run date 2026-04-14
- PUT entry returns Dataset (not EntryDetail); test verifies quantity_g via subsequent GET
