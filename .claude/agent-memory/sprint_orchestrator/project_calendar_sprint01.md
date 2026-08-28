---
name: Calendar Sprint01 Pattern
description: Atlas-owned timeblocking calendar; IMPLEMENTATION_IN_PROGRESS; container build required before test run; FullCalendar added to Atlas Shell
type: project
---

Calendar Sprint01_Core — Atlas-owned calendar blocks (NOT CalendarConnector which is Google Calendar adapter).

**Key facts:**
- Component: `03_Application/Calendar`
- Port: 8023 (host) → 8000 (container), container name `atlas-calendar`
- API prefix: `/api/cal` (distinct from CalendarConnector's `/api/calendar`)
- Test container: `atlas-calendar-test` (port 9023 in compose.test.yml)
- Shell basePath: `/calendar`

**State:** IMPLEMENTATION_IN_PROGRESS — container must be built before `sprint_test_runner` can execute.

**Why:** First run; `atlas-calendar-test` container does not exist yet. Must run:
```
docker compose -f 01_System/test/compose.test.yml --env-file 01_System/config.env --env-file 01_System/secrets.env up -d calendar-test --build
```

**Dependencies added:**
- `@fullcalendar/react`, `@fullcalendar/core`, `@fullcalendar/daygrid`, `@fullcalendar/timegrid`, `@fullcalendar/interaction` added to Atlas Shell `package.json`
- Shell Dockerfile COPY, main.tsx import, nginx.conf proxy, vite.config.ts proxy all wired

**Design review cycle:** asyncpg → psycopg2 correction required (one review cycle). Evidence: EVD-2026-05-07-001.

**How to apply:** When running test runner, expect fresh container build to take ~2 min. `npm install` needed in Atlas Shell before shell rebuild (new FullCalendar deps).
