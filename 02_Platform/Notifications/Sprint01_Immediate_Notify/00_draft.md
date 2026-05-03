# Sprint Draft — Notifications: Immediate Send for Claude Code

## Context

The Notifications platform service (`02_Platform/Notifications/`) already delivers FCM push notifications to the Android app through a scheduler-based path. The existing flow requires callers to:

1. Fetch the FCM token via `GET /api/devices/token`
2. POST a notification with `fire_at` and the raw FCM token in the body
3. Wait up to 30 seconds for the APScheduler polling loop to dispatch it

This works for application frontends scheduling reminders, but it is not suitable for Claude Code running in a terminal session, where:
- The caller should not need to handle FCM tokens (platform-internal detail)
- Dispatch must be immediate (sub-second), not deferred
- The call must be a single HTTP request

## Goal

Add a `POST /api/notifications/send` endpoint to the existing Notifications platform service that allows a single-step, immediate notification dispatch to the default Android device.

## Requirements

- Single HTTP call: POST with `{ title, body }` — no FCM token required from the caller
- Source field optional; defaults to `"claude"`
- Dispatch is immediate (synchronous FCM call in the request handler, not via scheduler)
- Notification record is persisted with status `dispatched` for audit
- Returns a minimal response: `{ id, title, body, dispatched_at }`
- Returns 503 if no device is registered (no FCM token stored for device_id="default")
- The endpoint is reachable at `http://localhost/api/notifications/send` from the host machine (covered by the existing nginx `/api/notifications` prefix route — no nginx change required)

## Notification content

The notification must support:
- `title` (required): short string, displayed as the Android notification title
- `body` (required): short string, displayed as the Android notification body text
- `source` (optional): identifier string, defaults to `"claude"`, stored for audit only

No deep_link, no buttons, no reply actions. Informational only.

## Out of scope

- Scheduling (fire_at)
- Deep links
- Multiple devices
- Any change to the Android app
- Any change to the existing `POST /api/notifications/` scheduling path
- Any change to nginx

## Caller contract (how Claude Code uses this)

```bash
curl -s -X POST http://localhost/api/notifications/send \
  -H "Content-Type: application/json" \
  -d '{"title": "Decision needed", "body": "Waiting on your input before proceeding."}'
```

Expected response (200):
```json
{
  "id": "<uuid>",
  "title": "Decision needed",
  "body": "Waiting on your input before proceeding.",
  "dispatched_at": "2026-04-15T12:00:00.123Z"
}
```
