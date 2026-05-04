# Test Spec — TaskTracker — Sprint10_CalendarBlocker

## Scope

Tests verify that creating or updating a scheduled task fires the correct CalendarConnector call (mocked), and that calendar errors never fail the task operation. Existing task CRUD correctness is covered by Sprint09 tests and is not re-tested here.

## Scenarios

### Create scheduled task triggers calendar create
- **Given:** CALENDAR_CONNECTOR_URL is set; CalendarConnector POST /api/calendar/events returns 201
- **When:** POST /api/tasks with {title: "Sprint Demo", status: "scheduled", scheduled_at: "2026-06-01", priority: "medium"}
- **Then:** The task is created (201-via-Dataset returned); CalendarConnector was called with atlas_event_id=task.id, all_day=true, start_at="2026-06-01", end_at="2026-06-02", title starting with "[Atlas] "

### Create non-scheduled task does not trigger calendar call
- **Given:** CALENDAR_CONNECTOR_URL is set; CalendarConnector is available
- **When:** POST /api/tasks with {title: "Open task", status: "open", priority: "low"}
- **Then:** Task is created successfully; CalendarConnector is never called

### Create scheduled task when CalendarConnector URL is empty skips sync silently
- **Given:** CALENDAR_CONNECTOR_URL is empty or not set
- **When:** POST /api/tasks with {title: "Quiet task", status: "scheduled", scheduled_at: "2026-06-01", priority: "medium"}
- **Then:** Task is created successfully; no HTTP call to CalendarConnector is attempted

### Patch task from open to scheduled triggers calendar create
- **Given:** An existing task with status=open; CALENDAR_CONNECTOR_URL is set; CalendarConnector returns 201
- **When:** PATCH /api/tasks/{id} with {status: "scheduled", scheduled_at: "2026-06-10"}
- **Then:** Task is updated (200 Dataset); CalendarConnector POST was called with atlas_event_id=task.id, start_at="2026-06-10", end_at="2026-06-11"

### Patch scheduled task with new scheduled_at triggers calendar update
- **Given:** An existing task with status=scheduled, scheduled_at=2026-06-01; CALENDAR_CONNECTOR_URL is set; CalendarConnector PATCH returns 200
- **When:** PATCH /api/tasks/{id} with {scheduled_at: "2026-06-15"}
- **Then:** Task is updated (200 Dataset); CalendarConnector PATCH /api/calendar/events/{task_id} was called with start_at="2026-06-15", end_at="2026-06-16"

### Patch scheduled task with only unrelated field does not trigger calendar update
- **Given:** An existing task with status=scheduled, scheduled_at=2026-06-01, title="Meeting prep"; CALENDAR_CONNECTOR_URL is set
- **When:** PATCH /api/tasks/{id} with {priority: "high"} (no status, scheduled_at, or title change)
- **Then:** Task is updated (200 Dataset); CalendarConnector is never called

### Patch task from scheduled to open triggers calendar delete
- **Given:** An existing task with status=scheduled; CALENDAR_CONNECTOR_URL is set; CalendarConnector DELETE returns 200
- **When:** PATCH /api/tasks/{id} with {status: "open", scheduled_at: null}
- **Then:** Task is updated (200 Dataset); CalendarConnector DELETE /api/calendar/events/{task_id} was called

### Calendar create error does not fail task creation
- **Given:** CALENDAR_CONNECTOR_URL is set; CalendarConnector POST returns 503
- **When:** POST /api/tasks with {title: "Resilient task", status: "scheduled", scheduled_at: "2026-06-01", priority: "medium"}
- **Then:** Task is created and Dataset is returned with 200; no error propagated to caller

### Calendar network error does not fail task update
- **Given:** CALENDAR_CONNECTOR_URL is set; CalendarConnector is unreachable (connection refused)
- **When:** PATCH /api/tasks/{id} to transition from open to scheduled
- **Then:** Task is updated and Dataset is returned with 200; no error propagated to caller
