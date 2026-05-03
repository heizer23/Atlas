# Test Spec — Notifications — Sprint01_Immediate_Notify

## Scope

Tests cover the new POST /api/notifications/send endpoint: immediate synchronous FCM dispatch, audit persistence, and error responses. The existing scheduler path (POST /api/notifications/, dispatch job) is explicitly out of scope for this sprint's tests.

FCM calls are mocked at the `send_fcm_message` function level to avoid real Firebase calls in CI.

## Scenarios

### Happy path: immediate send succeeds

- **Given:** A device row exists for device_id='default' with a valid FCM token. FCM send_fcm_message is mocked to return a fake message ID without raising.
- **When:** POST /api/notifications/send with body `{"title": "Decision needed", "body": "Waiting on your input."}` (source omitted)
- **Then:** Response is 200 with JSON containing `id` (valid UUID), `title` = "Decision needed", `body` = "Waiting on your input.", `dispatched_at` (valid ISO-8601 datetime). A row exists in notifications.notification with status='dispatched', source='claude', fire_at IS NULL, label='', deep_link=''.

### Happy path: explicit source field

- **Given:** A device row exists for device_id='default'. FCM mocked to succeed.
- **When:** POST /api/notifications/send with body `{"title": "Alert", "body": "Check this.", "source": "atlas_shell"}`
- **Then:** Response is 200. The persisted notification row has source='atlas_shell'.

### Error: no default device registered

- **Given:** No row in notifications.device for device_id='default'.
- **When:** POST /api/notifications/send with body `{"title": "Hi", "body": "There"}`
- **Then:** Response is 503. Body matches ApiError envelope with code='NO_DEFAULT_DEVICE'.

### Error: FCM dispatch fails

- **Given:** A device row exists for device_id='default'. FCM send_fcm_message is mocked to raise an exception.
- **When:** POST /api/notifications/send with body `{"title": "Hi", "body": "There"}`
- **Then:** Response is 502. Body matches ApiError envelope with code='FCM_DISPATCH_FAILED'. No notification row is written to Postgres.

### Validation: missing required fields

- **Given:** Any device state.
- **When:** POST /api/notifications/send with body `{"title": "Hi"}` (body field missing)
- **Then:** Response is 422 (FastAPI validation error). No FCM call is made. No notification row is written.
