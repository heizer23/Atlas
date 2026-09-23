---
name: atlas-calendar-app
description: >
  Read and write Atlas-owned calendar blocks (timeblocking view inside Atlas Shell).
  Use when the user wants to see their Atlas calendar, schedule a task block, create a
  personal time block, or view/edit/delete blocks in the Atlas Calendar.
  This is NOT Google Calendar — use atlas-calendar for that.
  Triggers on phrases like "schedule task", "add a time block", "block time for",
  "what's on my Atlas calendar", "show my blocks", "create a calendar block",
  "link task to calendar", "delete the block", "move the block", "reschedule".
  Base URL: http://atlas-calendar:8000/api/cal (no trailing slash).
  IMPORTANT: Read this SKILL.md before every calendar-app operation — do not guess
  endpoints from memory. Do NOT use atlas-calendar (CalendarConnector) for Atlas-owned
  blocks — that skill is for Google Calendar only.
---

# Atlas Calendar App

Read and write Atlas-owned calendar blocks via the Atlas Calendar HTTP API.
These blocks live in Atlas Postgres and are displayed in the Atlas Shell calendar view (`/calendar`).

## Important

This service manages **Atlas-owned time blocks** — not Google Calendar events.
Use the `atlas-calendar` skill if you need to read or write Google Calendar.

When scheduling a task, create a block here with `event_type: "task_block"` and link it via `source_object_id`.

## Base URLs

```
# Inside Docker on atlas-net (preferred):
http://atlas-calendar:8000/api/cal

# From the host:
http://localhost:8023/api/cal
```

---

## Endpoints

### List events
```
GET /cal/events
```

Optional query params: `from=<ISO8601>`, `to=<ISO8601>` (filter by time range).

Returns a Dataset with `object_type: calendar_event`.

Row fields:

| Field               | Type   | Notes                                          |
|---------------------|--------|------------------------------------------------|
| `id`                | string | UUID                                           |
| `title`             | string |                                                |
| `start_at`          | string | ISO8601 with timezone                          |
| `end_at`            | string | ISO8601 with timezone                          |
| `event_type`        | string | `task_block`, `personal_block`, or `blocker`   |
| `source_object_type`| string | `task` or null                                 |
| `source_object_id`  | string | Task UUID if linked, otherwise null            |
| `notes`             | string | Optional free text                             |
| `created_at`        | string | ISO8601                                        |
| `updated_at`        | string | ISO8601                                        |

---

### Create event
```
POST /cal/events
Content-Type: application/json
```

```json
{
  "title": "Block title",
  "start_at": "2026-05-16T10:00:00+02:00",
  "end_at": "2026-05-16T11:00:00+02:00",
  "event_type": "task_block",
  "source_object_type": "task",
  "source_object_id": "<task-uuid>",
  "notes": null
}
```

- `event_type` required: `task_block` | `personal_block` | `blocker`
- `source_object_type` / `source_object_id`: both must be set or both null
- `start_at` must be before `end_at`
- Returns Dataset with the created event

---

### Update event (partial)
```
PATCH /cal/events/{event_id}
Content-Type: application/json
```

All fields optional — include only what changes:

```json
{
  "title": "Updated title",
  "start_at": "2026-05-16T14:00:00+02:00",
  "end_at": "2026-05-16T14:30:00+02:00"
}
```

Omitted fields are unchanged. Explicit `null` clears a nullable field (e.g. `notes`).

Returns Dataset with updated event.

---

### Delete event
```
DELETE /cal/events/{event_id}
```

Returns 204 (no body) on success.
Deleting a block does NOT delete the linked task.

---

## Common Workflows

**Schedule a task as a time block:**
```
POST /cal/events
{
  "title": "<task title>",
  "start_at": "<ISO8601 with offset>",
  "end_at": "<ISO8601 with offset>",
  "event_type": "task_block",
  "source_object_type": "task",
  "source_object_id": "<task UUID>",
  "notes": null
}
```
Then PATCH the task status to `scheduled` via `atlas-tasks`.

**Block personal time:**
```
POST /cal/events
{
  "title": "Focus time",
  "start_at": "...",
  "end_at": "...",
  "event_type": "personal_block",
  "source_object_type": null,
  "source_object_id": null,
  "notes": null
}
```

**View today's blocks:**
```
GET /cal/events?from=2026-05-16T00:00:00Z&to=2026-05-16T23:59:59Z
```

**Reschedule a block:** PATCH with new `start_at` and `end_at`.

**Remove a block:** DELETE by event `id`.

---

## Error Handling

All errors follow the Atlas `ApiError` envelope:
```json
{ "error": { "code": "...", "message": "..." } }
```

| Code               | Meaning                                    |
|--------------------|--------------------------------------------|
| `NOT_FOUND`        | Event does not exist                       |
| `VALIDATION_ERROR` | Invalid field value or time ordering       |

---

## Notes

- No authentication required. Network-restricted to `atlas-net` inside Docker.
- Do NOT access the database directly — use the HTTP API only.
- Deleting a calendar block never deletes the linked task.
- Timestamps should include a timezone offset (e.g. `+02:00` for CEST).
