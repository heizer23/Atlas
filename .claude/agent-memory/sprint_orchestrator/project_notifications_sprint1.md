---
name: Notifications Sprint1 Pattern
description: First Platform-layer Notifications sprint; two-agent (Atlas Claude / Android Claude) delivery split via FCM payload boundary; Sprint01_Immediate_Notify adds immediate-send endpoint; test container uses Dockerfile.test + sleep infinity
type: project
---

## Sprint1_MVP (original Notifications MVP)

Sprint1_MVP for Workouttracker under 02_Platform/Notifications is the first sprint in this component.

Key structural facts:
- Layer: 02_Platform — designer must be sprint_design_platform
- Two coordinated delivery agents: Atlas Claude (server-side) and Android Claude (Android shell)
- FCM payload contract is the explicit boundary artifact
- No sprint_conventions.md at Notifications root — canonical R-PRO-BP-01 applies

## Sprint01_Immediate_Notify (2026-04-15)

Adds POST /api/notifications/send — single-step immediate FCM dispatch for Claude Code callers.

**State when last seen:** IMPLEMENTATION_IN_PROGRESS — awaiting test container rebuild.

**Required human action before test run:**
```
make -C /home/linse/Prod/Atlas/01_System test-up
# or targeted:
docker compose -f /home/linse/Prod/Atlas/01_System/test/compose.test.yml --env-file 01_System/config.env --env-file 01_System/secrets.env up -d notifications-test --build
docker exec atlas-notifications-test pytest tests/ -v
```

**Key implementation facts:**
- Schema migration: Sprint01_Immediate_Notify/10_schema.sql makes fire_at/label/deep_link nullable
- dispatched_at is captured in application code after FCM success (not a DB column)
- No DB write on FCM failure (502 path returns immediately)
- Test container: Dockerfile.test (sleep infinity CMD, no FCM creds needed)
- compose.test.yml updated to reference Dockerfile.test for notifications-test
- Tests mock init_fcm + start_scheduler at session scope in conftest

**How to apply:** Future Notifications sprints inherit this test pattern. The Dockerfile.test + sleep infinity approach is now the pattern for any platform service that has startup-time external credential requirements.
