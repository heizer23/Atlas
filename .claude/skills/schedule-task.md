# Schedule Task Skill

Invoked as `/schedule-task [task_id] [start_at]`.

Creates a timed Google Calendar event for an Atlas task and marks the task as `scheduled`.

---

## Inputs

- **task_id** — UUID of the task. If not provided as an argument, ask the user.
- **start_at** — ISO-8601 datetime, e.g. `2026-05-06T09:00:00`. If not provided, ask the user.
- **duration_minutes** — optional. If not provided, derive from the task's `effort_hours` field (×60, min 15 min). Default to 60 min if `effort_hours` is also null.

---

## Step 1 — Fetch the task

```bash
curl -s http://localhost:8010/api/tasks/{task_id}
```

If the response is an error or the task is not found, report it and stop.

Extract: `title`, `description`, `effort_hours`.

---

## Step 2 — Compute duration

```
if duration_minutes provided → use it
else if effort_hours is not null → max(15, effort_hours * 60)
else → 60
```

---

## Step 3 — Compute times

Parse `start_at` as a local datetime. Compute `end_at = start_at + duration_minutes`.

Format both as ISO-8601 with offset, e.g. `2026-05-06T09:00:00+02:00`.

Extract `scheduled_date` as `YYYY-MM-DD` (the date portion of `start_at`).

---

## Step 4 — Create calendar event

```bash
curl -s -X POST http://localhost:8021/api/calendar/events \
  -H "Content-Type: application/json" \
  -d '{
    "atlas_event_id": "<task_id>",
    "title": "[Atlas] <title>",
    "start_at": "<start_iso>",
    "end_at": "<end_iso>",
    "description": "Atlas task: https://workout.linspad.net/tasks/<task_id>\n\n<description>",
    "all_day": false
  }'
```

If the response is not 200/201, note it but continue — calendar errors are non-fatal.

---

## Step 5 — Update task status

```bash
curl -s -X PATCH http://localhost:8010/api/tasks/{task_id} \
  -H "Content-Type: application/json" \
  -d '{"status": "scheduled", "scheduled_at": "<scheduled_date>"}'
```

If this fails, report the error clearly — this is the critical step.

---

## Step 6 — Report

Tell the user:
- Task title and scheduled date
- Calendar event status (created / existing / error)
- Duration used
