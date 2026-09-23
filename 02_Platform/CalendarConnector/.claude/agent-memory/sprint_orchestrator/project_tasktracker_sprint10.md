---
name: TaskTracker Sprint10 Pattern
description: Calendar blocker sprint — scheduled task status wires to CalendarConnector best-effort; IMPLEMENTATION_IN_PROGRESS; container rebuild required before test run
type: project
---

TaskTracker Sprint10_CalendarBlocker is at IMPLEMENTATION_IN_PROGRESS.

**Why:** Wires scheduled task status to CalendarConnector — create/update/delete all-day events on task status transitions. Best-effort, non-blocking. No schema change, no frontend change.

**Key decisions:**
- `task.id` used directly as `atlas_event_id` (no LinkingEngine)
- `CALENDAR_CONNECTOR_URL` empty = silent skip (graceful degradation)
- Calendar sync fires after `conn.commit()`, never inside DB transaction
- Pre-update snapshot SELECT expanded to include `title` and `description` for change detection
- No calendar cleanup on task DELETE (accepted deferred decision)

**How to apply:** Container rebuild required before test run:
```
docker compose -f 01_System/test/compose.test.yml --env-file 01_System/config.env --env-file 01_System/secrets.env up -d tasktracker-test --build
docker exec atlas-tasktracker-test pytest tests/ -v
```
Test file: `03_Application/TaskTracker/tests/test_calendar_blocker.py`
Tests mock `_calendar_client` via `unittest.mock.patch` — CalendarConnector is not actually called in tests.
