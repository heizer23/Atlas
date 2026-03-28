---
name: Notifications Sprint1 Spec Review
description: Spec readiness review for 02_Platform/Notifications Sprint1_MVP for Workouttracker — verdict READY after resolving three blocking attention points
type: project
---

## Sprint
02_Platform/Notifications/Sprint1_MVP for Workouttracker

## Verdict
READY

## Key Decisions Resolved in design_specs.md

### 1. Scheduling mechanism
APScheduler BackgroundScheduler, in-process with FastAPI, 5-second IntervalTrigger polling `notifications.notification` for `fire_at <= now() AND status = 'pending'`. No external broker. Memory job store. Dispatcher logs id, fire_at, dispatched_at, delta_ms at INFO.

### 2. FCM payload contract
Data-only FCM message (no `notification` key). Five fields: `notification_id`, `title`, `body`, `label`, `deep_link`. Required design artifact: `20_design/fcm_payload_contract.json` (version 1.0). This is a required input for Android Claude — Android Claude implementation must not start without it.

### 3. Observability
No metrics/monitoring required for MVP. Dispatch logging (4 fields at INFO) using existing `platform_errorhandling` logging is sufficient against the 2-second timing tolerance acceptance criterion.

## Additions to Draft Data Contract
- `fcm_token` (string, platform-internal, non-user-visible) — required for dispatch, was missing from draft
- `status` (enum: pending/dispatched/cancelled/failed) — required for idempotency guard in dispatch loop

## Key Atlas Alignment Notes
- This component has no web UI surface — Atlas UI Data Contract (R-CON-BP-04) does not apply
- Platform boundary (R-CON-PL-01) requires notification endpoints in a standalone Platform service at `02_Platform/Notifications/backend/`, not embedded in WorkoutTracker router
- `platform_errorhandling` must be used for all API error responses — no ad-hoc formats
- Three required design artifacts (not two): `architecture.json`, `scaffolding.json`, `fcm_payload_contract.json`
