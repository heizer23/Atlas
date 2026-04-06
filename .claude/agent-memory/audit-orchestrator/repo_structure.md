---
name: Repository Structure Snapshot
description: Registered applications, platform components, and their current sprint states as of 2026-04-06
type: project
---

Snapshot as of 2026-04-06. Verify against current sprint_state.json files before acting on this.

## Applications (03_Application)

| App | Active Sprint | Sprint State | Notes |
|-----|-------------|-------------|-------|
| TaskTracker | Sprint02 — Optimization and Effort | AWAITING_HUMAN_REVIEW | Awaiting implementation-reviewer |
| TaskTracker | Sprint03 — Chronos Access | DRAFT_READY (no sprint_state.json) | Not yet orchestrated |
| WorkoutTracker | None | N/A | Pre-sprint-process era; implemented |
| FoodTracker | Sprint04 — Standard Dishes | DESIGN_APPROVED | Ready for implementation |
| Chronicle | Sprint01 — First Heatmap | AWAITING_HUMAN_REVIEW | Human gate and next_recommended_agent need correction |
| Chronicle | Sprint02 — Swimlanes and Selector | DRAFT_READY | Not yet designed |

## Platform Components (02_Platform)

| Component | Active Sprint | Sprint State | Notes |
|-----------|-------------|-------------|-------|
| CalendarConnector | Sprint03 — Edit and Delete | IMPLEMENTATION_IN_PROGRESS | next_recommended_agent needs correction |
| CalendarConnector | Sprint4 — Improved Skills | DRAFT_READY (no sprint_state.json) | Chronos feedback as input |
| Notifications | Sprint1 — MVP for Workouttracker | IMPLEMENTATION_IN_PROGRESS | Awaiting human gate |
| Notifications | Sprint2 — Firebase improvement | DRAFT_READY (no sprint_state.json) | Not yet orchestrated |
| Atlas_Shell | No active sprint | Deployed | 3 registered exceptions (EXC-PC-01/02/03) |
| MCPGateway | No active sprint | Deployed | Unregistered exception: imports from foodtracker.tools |
| Postgres | No active sprint | Deployed | Handles all app schemas via migrations |
| Chronos | No active sprint | Deployed | AI agent runtime at 02_Platform/Chronos/ |

## Sprint Conventions

- FoodTracker: has `sprint_conventions.md` — skips 10_specs/ stage
- Chronicle: no `sprint_conventions.md` — Sprint02 incorrectly claims FoodTracker convention applies
- TaskTracker: no `sprint_conventions.md` — Sprint02 had a one-off user-approved skip of specs-readiness stage

## Architecture Exceptions

- Atlas Shell: R-EXC-PC-01 (app nav in platform), R-EXC-PC-02 (lazy import pattern), R-EXC-PC-03 (ShellErrorBoundary request_id)
- FoodTracker: EXC-FT-01 through EXC-FT-05 (non-Dataset endpoint shapes)
- Chronicle: EXC-CH-01 (non-Dataset calendar endpoints)
- MCPGateway: UNREGISTERED — imports foodtracker.tools from Application layer
