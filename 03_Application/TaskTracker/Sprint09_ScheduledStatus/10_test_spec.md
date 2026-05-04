# Test Spec — TaskTracker — Sprint09_ScheduledStatus

## Scope

Tests cover the new `scheduled` status lifecycle: view=scheduled endpoint, auto-promotion behavior on active/pending_board page load, validation rules for scheduled_at, and PATCH semantics for clearing scheduled_at. UI behavior is out of scope for automated tests in this sprint.

## Scenarios

### Scheduled view returns scheduled tasks ordered by scheduled_at ASC
- **Given:** Two tasks exist with status=scheduled: task A with scheduled_at two days from now, task B with scheduled_at one day from now
- **When:** GET /api/tasks?view=scheduled is called
- **Then:** Response is a Dataset containing exactly task B then task A (ascending scheduled_at order); no non-scheduled tasks appear

### Scheduled view returns empty Dataset when no scheduled tasks exist
- **Given:** No tasks with status=scheduled exist
- **When:** GET /api/tasks?view=scheduled is called
- **Then:** Response is a Dataset with rows=[] and total=0

### Auto-promotion promotes past-due scheduled task on active view fetch
- **Given:** A scheduled task exists with scheduled_at set to yesterday (server UTC)
- **When:** GET /api/tasks?view=active is called
- **Then:** The formerly-scheduled task now has status=in_progress and appears in the active view response

### Auto-promotion does not promote future scheduled task on active view fetch
- **Given:** A scheduled task exists with scheduled_at set to tomorrow (server UTC)
- **When:** GET /api/tasks?view=active is called
- **Then:** The scheduled task is NOT promoted; it does not appear in the active view response

### Active view excludes future scheduled tasks
- **Given:** A scheduled task exists with scheduled_at set to tomorrow (server UTC)
- **When:** GET /api/tasks?view=active is called
- **Then:** The scheduled task is not in the response rows

### Create task with status=scheduled and scheduled_at succeeds
- **Given:** No precondition
- **When:** POST /api/tasks with body {title: "Plan review", status: "scheduled", scheduled_at: "<future ISO datetime>"}
- **Then:** Response is a Dataset with the created task; task has status=scheduled and the provided scheduled_at value

### Create task with status=scheduled and missing scheduled_at returns 400
- **Given:** No precondition
- **When:** POST /api/tasks with body {title: "Plan review", status: "scheduled"} (no scheduled_at)
- **Then:** Response is a 400 ApiError with code VALIDATION_ERROR

### PATCH task to scheduled status with scheduled_at succeeds
- **Given:** An existing open task
- **When:** PATCH /api/tasks/{task_id} with body {status: "scheduled", scheduled_at: "<future ISO datetime>"}
- **Then:** Response is a Dataset with the task at status=scheduled and the provided scheduled_at

### PATCH clears scheduled_at when status changes away from scheduled (explicit null)
- **Given:** An existing task with status=scheduled and a non-null scheduled_at
- **When:** PATCH /api/tasks/{task_id} with body {status: "open", scheduled_at: null}
- **Then:** Response is a Dataset with the task at status=open and scheduled_at=null

### Create task with scheduled_at provided but non-scheduled status is accepted
- **Given:** No precondition
- **When:** POST /api/tasks with body {title: "Note", status: "open", scheduled_at: "<future ISO datetime>"}
- **Then:** Response is a Dataset with the created task; task has status=open and the scheduled_at is stored (not rejected)

### [UI — manual] Scheduled tab renders tasks with formatted scheduled time
- **Given:** At least one task exists with status=scheduled and a non-null scheduled_at
- **When:** The user navigates to the Scheduled tab (via the tab bar)
- **Then:** The Scheduled tab is visible in the tab bar (order: Active | Scheduled | Pending | Done); the scheduled task row displays the task title, the scheduled time formatted as "Mon 5 May 09:00", and a priority chip; tapping the row opens the TaskDetailEdit panel showing the scheduled_at datetime-local field

### [UI — manual] Create form shows scheduled_at input when scheduled status selected
- **Given:** The user opens the task create form
- **When:** The user selects "Scheduled" from the status dropdown
- **Then:** A datetime-local input for scheduled_at appears and is required; submitting without a scheduled_at value is prevented by the form

### [UI — manual] Task detail clears scheduled_at when status changed away from scheduled
- **Given:** A task with status=scheduled is open in the TaskDetailEdit panel
- **When:** The user changes the status dropdown to "Open" and saves
- **Then:** The saved task has status=open and scheduled_at is cleared (null); the task no longer appears on the Scheduled tab
