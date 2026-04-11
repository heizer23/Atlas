# Sprint 03 — StorageTracker Notifications and Geofencing

## Goal

Remind the user at the right moment and place. Tasks are already the owner of actionable state. This sprint adds trigger conditions to tasks and a notification delivery mechanism. The user gets a practical reminder when near a useful store.

## Component

- Name: StorageTracker
- Layer: 03_Application
- Existing component — Sprint 03 extends Sprint 02

## Design decisions from prior sprints

- ShoppingTasks exist and carry source_tags (which stores the item can be bought at).
- Items are the truth; tasks are derived.
- StorageTracker does not become the geofencing engine — it provides data; triggering logic is external.

## What this sprint adds

### 1. NotificationTrigger

A **NotificationTrigger** links a shopping task to a condition under which the user should be reminded. Fields:
- `id`
- `task_id` — FK to shopping task (one task can have multiple triggers)
- `trigger_type` — `location` | `time`
- `trigger_value` — for `location`: the store/source tag name (e.g. "Rewe"); for `time`: an ISO datetime string
- `enabled` — boolean, default true
- `last_fired_at` — nullable timestamp; prevents repeated firing
- `created_at`

### 2. NotificationLog

A **NotificationLog** records every notification that was sent. Fields:
- `id`
- `trigger_id`
- `task_id`
- `fired_at`
- `channel` — `push` | `in_app` (for MVP, only `in_app` is implemented)
- `message` — the text that was sent

### 3. Location check endpoint

An external system (e.g. Chronos or a mobile app) can call:
- `POST /notifications/check-location` — body: `{ "location_label": "Rewe" }`
  - returns a list of open shopping tasks whose triggers include this location
  - fires in_app notifications for matching triggers (creates NotificationLog entries)
  - sets `last_fired_at` on each triggered trigger to now (rate limit: do not fire the same trigger if it fired within the last 2 hours)

### 4. Scheduled time trigger check

- `POST /notifications/check-time` — no body; checks all time triggers where `trigger_value` <= now and `last_fired_at` is null or > 2 hours ago; fires matching ones.

This endpoint is designed to be called by an external scheduler (Chronos cron or similar) — not by the user directly.

### 5. In-app notification surface

- `GET /notifications` — list recent NotificationLog entries for the user (last 50, ordered by fired_at desc)
- `DELETE /notifications/{id}` — dismiss a specific notification

### 6. Trigger management

- `POST /shopping-tasks/{task_id}/triggers` — add a trigger to a task
- `GET /shopping-tasks/{task_id}/triggers` — list triggers for a task
- `DELETE /triggers/{id}` — remove a trigger
- `PATCH /triggers/{id}` — enable/disable a trigger

## UI additions

- **Notification panel** — a small indicator in the shell showing recent in-app notifications; clicking opens a list.
- From **Shopping List** view: each task row shows a "Set reminder" button that opens a trigger creation form (choose type: location or time).
- **Notifications view** — list of recent fired notifications with dismiss button.

## Boundary

StorageTracker stores trigger conditions and logs fired notifications. It does NOT implement:
- Push notification delivery (no APNS, FCM, web-push)
- Geolocation polling (the external caller provides location)
- The scheduling loop (Chronos handles calling check-time)

## Open questions for designer to resolve

- Should NotificationTrigger be scoped to task or item? Prefer: task — tasks are the actionable unit.
- Rate limit of 2 hours: should this be configurable per trigger or global? Prefer: global constant for MVP, put it in app config.
- What happens to triggers when a task is completed or dismissed? Prefer: cascade delete triggers when task is closed.
- Should `check-location` return the notification log entries it just created, or just a count? Prefer: return the full list of fired notifications as Dataset so the caller can display them.
- Should in-app notifications auto-expire? Prefer: keep last 200 per-application, drop older ones on insert (simple ring buffer logic in the service layer).
