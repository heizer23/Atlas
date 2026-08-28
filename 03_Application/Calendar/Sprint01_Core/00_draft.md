# Sprint Draft — Calendar MVP: Task Timeblocking

## Goal

Create a new Atlas Calendar application that provides a basic timeblocking view for tasks.

Atlas should own calendar blocks. External calendars are not synced in this sprint.

## Layer

03_Application

## Component

Calendar

## Scope

Build a minimal calendar application using FullCalendar React.

The application must allow the user to:
- view calendar blocks in week/day view
- create a calendar block
- edit block title, start time, end time
- drag/resize blocks in the calendar UI
- delete a calendar block
- link a block to an existing TaskTracker task

## Out of Scope

- Google Calendar export
- Outlook integration
- recurrence
- attendees
- notifications
- automatic scheduling
- capacity planning
- task drag-and-drop from task list
- multi-user calendars
- public sharing

## Data Model

### CalendarEvent

Fields:
- id
- title
- start_at
- end_at
- event_type: `task_block | personal_block | blocker`
- source_object_type: `task | null`
- source_object_id: `task_id | null`
- notes
- created_at
- updated_at

Rules:
- A CalendarEvent may link to one task.
- A task may have multiple CalendarEvents.
- Deleting a CalendarEvent must not delete the linked task.
- Updating a CalendarEvent must not update the linked task.
- `start_at` must be before `end_at`.

## API

Required endpoints:

```text
GET    /api/calendar/events
POST   /api/calendar/events
PATCH  /api/calendar/events/{event_id}
DELETE /api/calendar/events/{event_id}

Rules:

GET /api/calendar/events returns Dataset.
Mutation success returns Dataset for create/update, empty Dataset or 204 for delete.
Errors use ApiError.
PATCH must distinguish omitted fields from explicit null.
UI

Use FullCalendar React.

Required UI behavior:

show week view by default
allow switching to day view
render Atlas-owned events
drag event to update start/end
resize event to update end
click event to edit/delete
create new event by selecting a time range
Task Linking

The event edit form must allow optional linking to a TaskTracker task by task id.

MVP is allowed to use a simple text input for task id.

No task search UI required in this sprint.

Acceptance Criteria
Calendar page is reachable from Atlas Shell.
User can create a standalone calendar block.
User can create a calendar block linked to a task.
User can move and resize a block.
User can delete a block without deleting the task.
GET /api/calendar/events returns Dataset-compatible data.
Calendar events persist in Postgres.