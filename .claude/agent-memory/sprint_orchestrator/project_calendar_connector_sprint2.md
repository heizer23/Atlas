---
name: CalendarConnector Sprint02 Pattern
description: Platform-layer write capability sprint; OAuth scope upgrade + new endpoint + decision log; AWAITING_HUMAN_REVIEW with two operator deployment actions required
type: project
---

CalendarConnector Sprint02-Writing Skill completed design+implementation pass on 2026-04-05. Sprint is at AWAITING_HUMAN_REVIEW — human gate not yet recorded.

**Why:** Extends Sprint01 (read-only Google Calendar) to write-capable via POST /api/calendar/events to a fixed operator-configured target calendar.

**Key decisions made:**
- `CALENDAR_TARGET_CALENDAR_ID` stored as env var in config.env (not DB) — operator must supply value before deployment
- New `calendar_decision_log` table in `migrations/002_write_capability.sql`
- `all_day` optional bool in write request — date-only format when true
- OAuth scope upgraded from `calendar.readonly` to `calendar` in google_oauth.py `_CALENDAR_SCOPE`
- INSUFFICIENT_SCOPE check uses token-split comparison (not substring) to correctly distinguish calendar vs calendar.readonly scope strings
- Decision log is best-effort: DB failures never propagate to caller
- `init_schema()` fixed to run all .sql files in migrations/ sorted by filename (was hardcoded to 001_init.sql only)
- Startup fail-fast for CALENDAR_TARGET_CALENDAR_ID (RuntimeError in on_startup)
- POST response is JSONResponse 201 with CalendarCreateEventResult (not Dataset — create operations are exempt from Dataset contract)

**Operator actions required before end-to-end testing:**
1. Set `CALENDAR_TARGET_CALENDAR_ID` in `01_System/config.env` to the Chronos Google Calendar ID
2. Re-run `GET /api/calendar/google/connect/start` to re-consent with expanded scope

**How to apply:** When routing future CalendarConnector sprints, check that both operator actions above are completed before marking SPRINT_COMPLETE. The CALENDAR_TARGET_CALENDAR_ID value is intentionally blank in config.env — it must be filled before deployment.
