# Agent Pass: Architecture and Structure Reviewer
**Run:** full_auditrun_04_06_2026
**Date:** 2026-04-06
**Agent function:** Layer placement, boundary violations, dependency direction

---

## Evidence Examined

- `00_Blueprint/Atlas_Manifest.md`
- `02_Platform/02_Atlas_Shell/ARCHITECTURE_EXCEPTIONS.md`
- `02_Platform/MCPGateway/app/main.py`
- `02_Platform/packages/platform_contracts/contracts.py`
- `02_Platform/packages/platform_contracts/CLAUDE.md`
- `02_Platform/Chronos/compose.yml`
- `01_System/config.env`
- `03_Application/TaskTracker/` — full directory
- `03_Application/WorkoutTracker/backend/routers/workout.py`
- `03_Application/FoodTracker/` — sprint records and backend structure
- `03_Application/Chronicle/` — sprint records and backend structure
- `00_Blueprint/SharedViews/chronicle.sql`

---

## Findings

### PASS — Four-layer structure respected

All components examined are correctly placed in their layer:
- Blueprint: Manifest, rule registry, shared SQL views
- System: Config, AtlasPhone, Makefile, bootstrap, Chronos runtime
- Platform: Postgres, Atlas Shell, CalendarConnector, Notifications, MCPGateway, platform packages
- Application: TaskTracker, WorkoutTracker, FoodTracker, Chronicle

No component was found outside the four-layer structure.

### PASS — Platform components contain no domain logic

`platform_contracts/contracts.py`: defines Dataset, DatasetMeta, ColumnSchema — purely structural. No domain fields.
`platform_errorhandling/`: error utilities only. No domain logic.
`Notifications/`: is a platform service for push delivery. It receives content from callers; it does not interpret or assign domain meaning to notification content. Boundary is respected.
`CalendarConnector/`: provides Google Calendar integration. It stores calendar events with a stable `atlas_event_id` slug and writes to a designated calendar. It does not interpret the meaning of events for any application. Boundary respected.
`MCPGateway/`: registers application-exposed tool functions and provides the MCP protocol layer. The tool implementations (`foodtracker/tools.py`) live in the Application layer; MCPGateway imports them. This pattern is formally registered (EXC-PC-02 analogy applies to import direction) — the application tools are thin functions, not gateway internals.

### WARNING — MCPGateway imports directly from application layer

`02_Platform/MCPGateway/app/main.py` imports `from foodtracker.tools import log_meal, get_nutrition_summary`. This is a Platform-to-Application import, violating R-CON-PL-02 (dependency direction). This violation is analogous to R-EXC-PC-02 (Shell lazy-importing Application) but has not been formally registered as an EXCEPTION.

The import is structurally necessary given the MCPGateway design — tools must be registered at MCP server startup. However, without a registered exception, this is an unregistered deviation.

**Consequence:** Future agents and auditors cannot determine whether this boundary violation is intentional or accidental. The FoodTracker tools.py file is also not referenced in any centrally-visible contract.

**Recommendation:** Register a `R-EXC-PC-04` in `02_Platform/MCPGateway/ARCHITECTURE_EXCEPTIONS.md` (or within the existing shell exceptions file) documenting this as an intentional, constrained deviation. Constrain it: MCPGateway may import only from `<app>/tools.py`-pattern files, not from application backend internals.

### PASS — Shared views are in Blueprint

`00_Blueprint/SharedViews/chronicle.sql` defines the cross-application view contract. Correct placement per Atlas Manifest §Contracts.

### PASS — Application table schemas are private

All application schemas (`tasktracker.tasks`, `workout.workout_log`, `foodtracker.food_logs`) live in their respective application migration files. None are referenced by other applications except through the `shared_views.calendar_event_view` (Blueprint contract). No cross-application table dependencies observed.

### PASS — Chronos is in the correct layer

Chronos (the AI agent runtime) is located at `02_Platform/Chronos/compose.yml`. However, `config.env` comments it as "System: Chronos." The directory placement in `02_Platform/` is correct per the four-layer model (it is a platform capability — an AI runtime that other components access). The config.env comment is slightly misleading but not a structural defect.

### INFO — WorkoutTracker has no active sprint folder

`03_Application/WorkoutTracker/` has implementation code but no sprint folder under the R-PRO-BP-01 format. This is consistent with its pre-R-PRO-BP-01 origins (the application predates the sprint process rule). No violation per the prospective application date.

### INFO — CalendarConnector Sprint4 has no sprint folder structure

`02_Platform/CalendarConnector/Sprint4 - Improved Skills/` contains only `00_input/draft.md`. The sprint process has not been initiated. The draft content (from Chronos feedback about missing skill capabilities) is pre-design input. No violation — `DRAFT_READY` is a valid initial state.

---

## Verdict

PASS with 1 warning. No blocking architecture violations.

| Severity | Finding |
|----------|---------|
| WARNING | MCPGateway imports from Application layer (`foodtracker.tools`) with no registered exception — deviation from R-CON-PL-02 is unregistered |
| INFO | WorkoutTracker has no sprint folder — consistent with pre-sprint-process origin, no violation |
| INFO | CalendarConnector Sprint4 is `DRAFT_READY` with only input draft present — expected state |
