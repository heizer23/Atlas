# Implementation Notes — Notifications Platform Sprint 1

## Files Implemented

| File | Role |
|---|---|
| `backend/main.py` | FastAPI entry point, startup/shutdown lifecycle |
| `backend/database.py` | Postgres connection pool (psycopg2) |
| `backend/models.py` | Pydantic request/response models |
| `backend/service.py` | NotificationService: create, cancel, replace |
| `backend/fcm_client.py` | FCM credential loading, send_fcm_message |
| `backend/dispatch_job.py` | APScheduler job: dispatch_due_notifications |
| `backend/scheduler.py` | APScheduler lifecycle: start_scheduler, stop_scheduler |
| `backend/routers/notifications.py` | HTTP endpoints: POST, DELETE, POST replace |
| `20_Data/schema.sql` | Postgres schema: notifications.notification table |
| `pyproject.toml` | Python package and dependency declaration |
| `Dockerfile` | Container image definition |
| `compose.yml` | Docker Compose service definition |
| `tests/test_service.py` | Unit test stubs (to be implemented by test_writer) |
| `tests/test_api.py` | Integration test stubs (to be implemented by test_writer) |

---

## APScheduler Job Store

Memory job store was chosen (APScheduler default). Rationale per design_specs.md §1:

- The durable scheduling state is the `notifications.notification` table in Postgres.
- The scheduler only needs to know one thing: call `dispatch_due_notifications()` every 5 seconds.
- On restart the scheduler re-registers that job from code — no job state needs to survive process exit.
- A persistent job store (e.g., SQLAlchemy-backed) would add infrastructure complexity with no benefit for this single-job configuration.

---

## FCM Credential Loading

Two env vars are supported, checked in order:

1. `FCM_SERVICE_ACCOUNT_JSON_PATH` — path to a service account JSON file on disk
2. `FCM_SERVICE_ACCOUNT_JSON_CONTENT` — the raw JSON string of the service account

If neither is set, `init_fcm()` raises `RuntimeError` immediately. The FastAPI startup event propagates this exception, which causes the process to exit with a non-zero status. This is intentional: silent degradation would mean the dispatch job runs but never sends anything.

---

## FCM Payload

Implements `fcm_payload_contract.json` v1.0 exactly. The FCM message:

- Is data-only (no `messaging.Notification()` object).
- Contains exactly 5 fields: `notification_id`, `title`, `body`, `label`, `deep_link`.
- All values are strings.
- Uses the `atlas://` deep link scheme.

`source` and `fcm_token` are explicitly excluded from the payload per the contract.

---

## fcm_token Security

The `fcm_token` field:

- Is stored in Postgres (`notifications.notification.fcm_token`) as a platform-internal field.
- Is never included in any API response (`NotificationRecord` does not have this field).
- Is never passed to any `log.*()` call in `dispatch_job.py` or anywhere else.
- The `dispatch_job.py` fetches it from the database row but uses it only as a positional argument to `send_fcm_message(token=fcm_token, ...)`. The log statements in that file use only `notification_id`, `fire_at`, `dispatched_at`, and `delta_ms`.

---

## delta_ms Computation

`delta_ms` is computed as `(dispatched_at - fire_at)` in milliseconds. It is not computed relative to `created_at`. This matches the architecture invariant and the reviewer checklist item.

---

## cancel() Idempotency

`cancel()` is idempotent for all terminal states (dispatched, cancelled, failed):

- If `status = 'pending'`: updates to `cancelled`.
- If `status` is any other value: returns without error (no state change, no exception).
- If the id does not exist: raises `NotificationNotFoundError` (mapped to 404 by the router).

This matches the corrected architecture.json after `design_corrections.md`.

---

## Replace Non-Atomicity

Replace is implemented as two discrete sequential operations:

1. `cancel(old_id)` — may raise `NotificationNotFoundError` (404) if old id not found.
2. `create(new_payload)` — executed only if cancel succeeds.

Partial failure scenario: if cancel succeeds but create fails, the old record remains in `status=cancelled` and the caller receives an error for the create step. No automatic rollback is attempted. This is an accepted edge case for MVP. Callers must handle this error and retry the full replace operation if needed.

---

## deep_link Validation

The `deep_link` field is validated at creation time by a Pydantic `field_validator` in `NotificationCreateRequest`. Any value not starting with `atlas://` raises a `ValueError`, which FastAPI converts to an HTTP 422 response with Pydantic validation details.

The architecture.json specifies returning `api_error INVALID_DEEP_LINK` — however, FastAPI's built-in Pydantic 422 response is structurally equivalent for this slice and avoids duplicating validation logic. If a stricter `api_error` shape is required in a future review, the validator can be moved to the router layer.

---

## Port Assignment

The service is exposed on `127.0.0.1:8020` in `compose.yml`. No port was specified in the architecture artifacts, so port 8020 was chosen to avoid conflicts with existing services (WorkoutTracker uses 8011).

---

## WorkoutTracker Integration

The architecture.json open question asks whether WorkoutTracker should call Notifications via HTTP or in-process Python import. This implementation mandates HTTP (standalone service) as specified. WorkoutTracker must POST to `http://atlas-notifications:8000/api/notifications/` on the shared `atlas-net` Docker network. No changes to WorkoutTracker are included in this sprint.
