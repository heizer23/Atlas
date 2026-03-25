Implement FCM device registration v1 for Atlas.

Goal:
Replace manual FCM token seeding with an authenticated Android → Atlas registration flow.

---

## Backend (Atlas)

Create a device registration endpoint.

POST /api/devices/register

Request:
{
  "device_id": string,
  "platform": "android",
  "fcm_token": string,
  "app_version": string (optional)
}

Behavior:
- authenticate request (reuse existing auth)
- upsert device by (device_id, platform)
- store latest fcm_token
- update last_seen_at
- idempotent (same input = safe)

Database:
table: platform.device_registration

fields:
- device_id (text)
- platform (text)
- fcm_token (text)
- last_seen_at (timestamp)
- created_at
- updated_at

unique:
(device_id, platform)

---

## Dispatch change

Update notification dispatch:
- read fcm_token from device_registration
- no manual token usage
- use latest token per device

---

## Android

On app start:
- obtain FCM token
- POST to /api/devices/register

On token refresh:
- re-send registration

Use existing auth/session if available.

---

## Rules

- no workout-specific logic
- no additional features
- no UI
- minimal implementation

---

## Acceptance

- Android starts → device registers automatically
- token stored in DB
- token updates overwrite previous value
- notifications are delivered without manual backend seeding