---
name: TaskTracker Sprint09 Pattern
description: Scheduled status feature (scheduled_at, auto-promotion, Scheduled tab); IMPLEMENTATION_IN_PROGRESS; container rebuild + migration 009 required before test run
type: project
---

Sprint09_ScheduledStatus adds `scheduled` task status with `scheduled_at timestamptz`.

**What was built:**
- Migration: `migrations/009_scheduled_status.sql` (status CHECK constraint expansion + column + partial index)
- `schema.sql` updated with idempotent Sprint09 ALTER statements
- `backend/routers/tasks.py`: VALID_STATUS/VALID_VIEW updated, `scheduled_at` in TaskCreate/TaskUpdate, `_run_auto_promotion()` helper, view=scheduled branch, auto-promotion before active/pending_board fetch
- `src/shellConfig.ts`: Scheduled tab added (order: Active|Scheduled|Pending|Done)
- `src/ShellEntry.tsx`: ViewTab type, viewFetchUrl, route detection, renderScheduledTab, datetime-local inputs in create/edit forms, `scheduled_at` in TaskRow
- `Dockerfile`: copies `tests/test_scheduled_status.py` into container's tests/ alongside PersonalDevelopment tests
- `tests/test_scheduled_status.py`: 9 API-level scenarios, self-sufficient (no fixtures.sql dependency)

**State:** IMPLEMENTATION_IN_PROGRESS

**Why:** Sprint09 is a clean extension of an existing component. No new service needed.

**How to apply:** Before test run, rebuild the atlas-tasktracker-test container and apply migration 009 to atlas_test. Test runner command: `docker exec atlas-tasktracker-test pytest tests/ -v`. Also rebuild atlas-tasktracker (prod) and the Atlas Shell for frontend changes.

**Migration note:** migration 009 drops and re-adds the tasks_status_check constraint. On an existing database this requires a brief table lock — acceptable for single-user deployment.

**Design review note:** First review was APPROVED_WITH_CHANGES (missing UI scenarios in test spec). Corrected by adding 3 [UI — manual] scenarios. Second review APPROVED.
