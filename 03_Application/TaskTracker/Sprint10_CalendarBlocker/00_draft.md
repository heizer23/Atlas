# Sprint 10 — Calendar Blocker

## Goal

Wire the `scheduled` task status to Google Calendar via CalendarConnector.
When a task is scheduled, an all-day calendar event is created automatically.
When the date changes, the event is updated. When the task leaves `scheduled`,
the event is deleted. Clicking the Google Calendar event deep-links back to
the task in Atlas.

No frontend changes in this sprint — all logic lives in the TaskTracker backend.

---

## Scope

**In scope:**
- Create a Google Calendar all-day event when a task transitions **to** `scheduled`
- Update the calendar event when `scheduled_at` changes on an already-scheduled task
- Delete the calendar event when a task transitions **away from** `scheduled`
- Include an Atlas deep link in the event description
- Add `CALENDAR_CONNECTOR_URL` and `ATLAS_BASE_URL` env vars to TaskTracker

**Out of scope:**
- Frontend changes
- LinkingEngine (the task ID is used directly as `atlas_event_id` — it is the stable 1:1 key)
- Sprint 11 (deep link routing — frontend route `/tasks/:id` for opening a task from URL)
- Sync in the reverse direction (changes made in Google Calendar flowing back to Atlas)

---

## Cross-system identity

`atlas_event_id` passed to CalendarConnector = `task.id` (UUID string).

This is valid because:
- One task has at most one calendar blocker at a time
- The task ID is stable and globally unique
- CalendarConnector already uses `atlas_event_id` as its idempotency key

No LinkingEngine entry is needed — the CalendarConnector's event index already
records the Google event ID keyed by `atlas_event_id`.

---

## CalendarConnector API used

All calls are HTTP to the internal `atlas-calendar-connector` service.

| Action | Endpoint | Notes |
|--------|----------|-------|
| Create blocker | `POST /api/calendar/events` | `all_day=true`, title = task title |
| Update blocker | `PATCH /api/calendar/events/{task_id}` | only when `scheduled_at` or `title` changed |
| Delete blocker | `DELETE /api/calendar/events/{task_id}` | on any transition away from `scheduled` |

CalendarConnector's create is idempotent by `atlas_event_id` — safe to call on retry.

---

## Event format

All-day event (`all_day=True`):
- `start_at`: `scheduled_at` in `YYYY-MM-DD` format
- `end_at`: `scheduled_at + 1 day` in `YYYY-MM-DD` format (Google all-day convention)
- `title`: task title, prefixed with `"[Atlas] "` for easy visual scanning
- `description`: `"Atlas task: https://workout.linspad.net/tasks/{task_id}\n\n{task_description or ''}"`
- `atlas_event_id`: task UUID string

---

## Backend changes

File: `backend/routers/tasks.py`

### New env vars

```python
CALENDAR_CONNECTOR_URL = os.environ.get("CALENDAR_CONNECTOR_URL", "")
ATLAS_BASE_URL         = os.environ.get("ATLAS_BASE_URL", "https://workout.linspad.net")
```

If `CALENDAR_CONNECTOR_URL` is empty, calendar calls are silently skipped (graceful
degradation — CalendarConnector may not be connected or OAuth may not be set up).

### New helper: `_calendar_client()`

Returns an `httpx.Client` pointed at `CALENDAR_CONNECTOR_URL`. Pattern mirrors
`_label_client()` and `_preference_client()`.

### New helper: `_sync_calendar_event(task_id, title, scheduled_at, description, action)`

`action` is one of `"create"`, `"update"`, `"delete"`.

- `"create"` / `"update"`: POST or PATCH to CalendarConnector; construct all-day date strings
- `"delete"`: DELETE to CalendarConnector
- All errors are logged but do not propagate to the caller — calendar sync is best-effort.
  The task operation always succeeds regardless of calendar outcome.
- If `CALENDAR_CONNECTOR_URL` is empty, returns immediately.

### `create_task` changes

After a successful INSERT, if `body.status == "scheduled"`:
- Call `_sync_calendar_event(task_id, title, scheduled_at, description, "create")`

### `update_task` changes

After a successful PATCH commit, evaluate calendar action:

| Transition | Action |
|------------|--------|
| Any status → `scheduled` (new) | `"create"` |
| `scheduled` → `scheduled`, `scheduled_at` or `title` changed | `"update"` |
| `scheduled` → any other status | `"delete"` |
| No status change, not currently `scheduled` | no-op |

To evaluate: read the pre-update snapshot (already fetched for validation) and compare
with the post-update state.

---

## compose.yml changes

Add to the `tasktracker` service environment:
```yaml
CALENDAR_CONNECTOR_URL: http://atlas-calendar-connector:8000
ATLAS_BASE_URL:         https://workout.linspad.net
```

---

## Deep link

The event description contains:
```
Atlas task: https://workout.linspad.net/tasks/{task_id}
```

Clicking this URL in Google Calendar opens the browser to that path.
Frontend routing for `/tasks/:id` is out of scope for this sprint — the URL is
planted now and will work once Sprint 11 adds the route.

---

## Error handling

- CalendarConnector unreachable → log warning, task operation succeeds
- CalendarConnector returns non-2xx → log warning with status code + body, task operation succeeds
- CalendarConnector not configured (`CALENDAR_CONNECTOR_URL=""`) → skip silently

No retry logic in this sprint. Retries can be added later if needed.

---

## Open questions (resolved)

| Question | Resolution |
|----------|------------|
| Use LinkingEngine? | No — task.id = atlas_event_id directly (1:1, stable) |
| Calendar event type | All-day (no time) — exact time is irrelevant to the task |
| Calendar sync failures | Best-effort, non-blocking — task always wins |
| What if CalendarConnector not connected? | Graceful skip via empty env var check |
| Deep link route functional this sprint? | No — URL planted, route added in Sprint 11 |
