---
name: Recurring Violation Patterns
description: Patterns observed across multiple components/sprints that are likely to recur — check these proactively in future audits
type: feedback
---

## Pattern 1: next_recommended_agent = null when sprint is not SPRINT_COMPLETE

**Found in:** CalendarConnector Sprint03 (IMPLEMENTATION_IN_PROGRESS), Chronicle Sprint01 (AWAITING_HUMAN_REVIEW)
**Rule:** R-PRO-BP-01 §9 — `next_recommended_agent` must be null only when `current_state` is `SPRINT_COMPLETE`
**Check:** In every sprint_state.json, verify this field is non-null unless state is SPRINT_COMPLETE

## Pattern 2: init_schema() DDL not kept in sync with schema.sql

**Found in:** TaskTracker database.py
**Risk:** Dual source of truth for the same schema. Agents reading one file will disagree with agents reading the other.
**Check:** Where init_schema() inline DDL exists, verify it matches the app's current schema.sql

## Pattern 3: sprint_conventions claimed without sprint_conventions.md

**Found in:** Chronicle Sprint02 sprint_state.json (claims FoodTracker convention applies)
**Rule:** R-PRO-BP-01 §7 — conventions apply per-application via the app's own sprint_conventions.md
**Check:** If sprint notes reference a convention from another app, verify the claiming app has its own sprint_conventions.md

## Pattern 4: Architecture exceptions not registered for Platform-to-Application imports

**Found in:** MCPGateway (imports foodtracker.tools)
**Analogy:** Same pattern as R-EXC-PC-02 (Shell lazy imports from Application)
**Check:** Any Platform component that imports from 03_Application must have a registered exception

## Pattern 5: CLAUDE.md references with stale or broken paths

**Found in:** TaskTracker CLAUDE.md (broken error handling path, broken AppDefinition reference)
**Check:** In application CLAUDE.md files, verify all referenced paths exist in the repo

## Pattern 6: human_gate_required=true but blocking=false

**Found in:** CalendarConnector Sprint02
**Risk:** Sprint appears not blocking when it cannot actually progress
**Check:** If human_gate_required=true and human_gate_recorded is false/missing, note this prominently regardless of blocking flag value

## Pattern 7: 0.0.0.0 bindings without documented rationale

**Found in:** Notifications (intentional for Android/Tailscale), Chronos (CHRONOS_BIND)
**Rule:** R-OPS-BP-02 — prefer most restricted configuration
**Check:** Any 0.0.0.0 binding should have a documented rationale in compose.yml comment, config.env comment, or a DEPLOYMENT_NOTES.md
