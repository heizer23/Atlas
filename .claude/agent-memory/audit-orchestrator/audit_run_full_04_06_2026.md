---
name: Full System Audit 2026-04-06
description: Key findings and institutional knowledge from the first full system audit — blocking items, warning patterns, coverage gaps
type: project
---

First full system audit run on 2026-04-06. Output at `01_System/AuditRuns/full_auditrun_04_06_2026/`.

## Blocking Findings

1. CalendarConnector Sprint03 sprint_state.json: `next_recommended_agent: null` with state IMPLEMENTATION_IN_PROGRESS — schema violation of R-PRO-BP-01 §9
2. Chronicle Sprint01 sprint_state.json: `next_recommended_agent: null` with state AWAITING_HUMAN_REVIEW — same violation
3. TaskTracker database.py `init_schema()` does not include `effort_hours` — diverges from `schema.sql` canonical reference (added in Sprint02). Migration bridges the gap in practice but creates dual source of truth.

**Why:** These were discovered during the sprint process and implementation review passes.
**How to apply:** In future audits, always check that `next_recommended_agent` is non-null unless state is `SPRINT_COMPLETE`. Check that `init_schema()` (where it exists) matches the app's `schema.sql`.

## Key Warnings

- MCPGateway imports from Application layer (`foodtracker.tools`) with no registered exception — needs R-EXC-PC-04
- Chronos binds to `0.0.0.0` (CHRONOS_BIND env var) — AI runtime with broader than minimal exposure; mitigated by token auth
- Notifications binds `0.0.0.0:8020` — intentional for Android/Tailscale but undocumented as accepted deviation
- TaskTracker CLAUDE.md has broken path reference (`02_Platform/03_ErrorHandling/` does not exist)
- TaskTracker `00_AppDefinition.md` deleted from root — CLAUDE.md reference broken; file moved to Sprint01 subfolder
- CalendarConnector Sprint02 human gate required but unrecorded (blocking: false despite gate not satisfied)
- Chronicle Sprint02 claims FoodTracker sprint_conventions apply — Chronicle has no sprint_conventions.md

## Coverage Gaps in This Audit

- FoodTracker Sprint04 implementation not started — deferred to post-Sprint04 audit
- Chronicle Sprint02 design not produced — deferred
- WorkoutTracker: no sprint artifacts (pre-sprint-process era); implementation reviewed directly
- platform_errorhandling internals not deeply audited
- AtlasPhone (Android app) not deeply audited
