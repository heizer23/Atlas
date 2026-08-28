# Test Spec — Calendar — Sprint01_Core

## Scope
Test the four CalendarEvent API endpoints (list, create, patch, delete). UI behavior and FullCalendar integration are out of scope for automated tests in this sprint.

## Scenarios

### List events returns Dataset
- **Given:** The database contains at least one CalendarEvent (fixture 'Morning Focus Block')
- **When:** GET /api/cal/events is called with no params
- **Then:** Response is 200; body is a Dataset with meta.object_type='calendar_event'; rows contains at least one entry; each row has id, title, start_at, end_at, event_type fields

### List events empty
- **Given:** The calendar_events table is empty
- **When:** GET /api/cal/events is called
- **Then:** Response is 200; Dataset with rows=[] and meta.total=0

### List events with date window filter
- **Given:** Fixtures include events inside and outside a date window
- **When:** GET /api/cal/events?start=2026-01-01T00:00:00Z&end=2026-01-08T00:00:00Z
- **Then:** Response is 200; only events with start_at >= 2026-01-01T00:00:00Z and start_at < 2026-01-08T00:00:00Z are returned

### Create standalone calendar block
- **Given:** No precondition
- **When:** POST /api/cal/events with body {title: "Standup", start_at: "2026-05-10T09:00:00Z", end_at: "2026-05-10T09:30:00Z", event_type: "personal_block"}
- **Then:** Response is 200; Dataset with single row; row.title="Standup"; row.event_type="personal_block"; row.id is a non-empty UUID string; row.source_object_id is null

### Create calendar block linked to a task
- **Given:** No precondition (task_id is a plain string reference, no FK enforcement)
- **When:** POST /api/cal/events with body {title: "Work on Sprint", start_at: "2026-05-10T10:00:00Z", end_at: "2026-05-10T11:00:00Z", event_type: "task_block", source_object_type: "task", source_object_id: "task-abc-123"}
- **Then:** Response is 200; Dataset single row; row.source_object_type="task"; row.source_object_id="task-abc-123"

### Create event where start_at >= end_at is rejected
- **Given:** No precondition
- **When:** POST /api/cal/events with body {title: "Bad", start_at: "2026-05-10T11:00:00Z", end_at: "2026-05-10T09:00:00Z", event_type: "personal_block"}
- **Then:** Response is 422; body is ApiError with error.code="CALENDAR_VALIDATION_ERROR"

### PATCH updates start_at and end_at
- **Given:** Fixture 'Morning Focus Block' exists with known id
- **When:** PATCH /api/cal/events/{fixture_id} with body {start_at: "2026-05-10T08:00:00Z", end_at: "2026-05-10T09:00:00Z"}
- **Then:** Response is 200; Dataset single row; row.start_at and row.end_at match the patched values; other fields unchanged

### PATCH with omitted fields leaves them unchanged
- **Given:** Fixture 'Task Linked Block' exists with title and notes set
- **When:** PATCH /api/cal/events/{fixture_id} with body {title: "Renamed"}
- **Then:** Response is 200; row.title="Renamed"; row.notes is unchanged from fixture value

### PATCH with explicit null clears notes
- **Given:** Fixture 'Task Linked Block' has non-null notes
- **When:** PATCH /api/cal/events/{fixture_id} with body {notes: null}
- **Then:** Response is 200; row.notes is null

### Delete event returns empty Dataset
- **Given:** Fixture 'Personal Block' exists with known id
- **When:** DELETE /api/cal/events/{fixture_id}
- **Then:** Response is 200; Dataset with rows=[] and total=0; subsequent GET /api/cal/events does not include the deleted event

### Delete non-existent event returns 404
- **Given:** No event exists with id "00000000-0000-0000-0000-000000000000"
- **When:** DELETE /api/cal/events/00000000-0000-0000-0000-000000000000
- **Then:** Response is 404; body is ApiError with error.code="CALENDAR_EVENT_NOT_FOUND"

### Delete task-linked event does not corrupt task reference
- **Given:** Fixture 'Task Linked Block' is linked to source_object_id="task-abc-123"
- **When:** DELETE /api/cal/events/{fixture_id}
- **Then:** Response is 200; the calendar event is gone; no error relating to task deletion; (task data is outside this application's scope — this test verifies the delete completes cleanly without cascade errors)

### [UI — manual] Week view renders events and allows navigation
- **Given:** The Calendar page is accessible from Atlas Shell at /calendar
- **When:** User navigates to /calendar
- **Then:** FullCalendar week view is displayed; Atlas-owned events from the API are rendered as blocks; user can navigate to next/previous week

### [UI — manual] Create event by selecting a time range
- **Given:** Calendar week view is open
- **When:** User selects a time range by dragging on the calendar
- **Then:** An event creation modal appears; user can fill in title and event_type; on save the event appears on the calendar

### [UI — manual] Drag event to update times
- **Given:** A calendar event is visible in the week view
- **When:** User drags the event to a new time slot
- **Then:** The event moves to the new time; the backend PATCH is called; the event persists at the new time after page reload

### [UI — manual] Click event to edit or delete
- **Given:** A calendar event is visible in the week view
- **When:** User clicks the event
- **Then:** An edit modal appears with the event's current fields; user can edit and save or delete the event
