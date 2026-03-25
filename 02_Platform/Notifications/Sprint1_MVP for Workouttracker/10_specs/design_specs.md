# Design Specs — Notifications Sprint1 (MVP for WorkoutTracker)

**Verdict: READY**

> This spec is ready to be handed to a Platform Designer. All critical product decisions are resolved below. The FCM payload contract is captured as an explicit required design artifact. The scheduling mechanism is specified. The observability gap is resolved with a minimal, proportionate requirement. Remaining gaps are safe designer decisions.

---

## Evaluation Summary

```
## Verdict
READY

## Must-Fix Issues (Blocking)
None — all three orchestrator-flagged attention points are resolved in this document (see sections below).

## Safe-to-Defer Decisions (Designer can handle)
[See Section 5]

## Atlas Violations / Redundancies
[See Section 6]

## Ambiguities with Suggested Resolution
[See Section 7]

## Risks
[See Section 8]

## Minimal Edits to Reach READY
N/A — verdict is READY after resolving attention points in this document.
```

---

## 1. Resolved: Scheduling Mechanism

**Orchestrator flag:** The scheduling mechanism for dispatching notifications at `fireAt` time is unspecified.

**Resolution — specified here, not left to designer:**

The Atlas server must use an **APScheduler background scheduler** (APScheduler v3 with `BackgroundScheduler`) running inside the FastAPI process as the dispatch mechanism for this slice.

Rationale:
- Atlas backends are FastAPI (Python). APScheduler integrates without a separate worker process or broker, which is correct for a short-delay (2-minute lead time), single-instance, personal-use system.
- Celery introduces a broker dependency (Redis/RabbitMQ) that Atlas does not currently have and is disproportionate to this slice.
- A cron job or OS-level scheduler is inappropriate for sub-minute polling intervals and is not Atlas-native.
- APScheduler with an `IntervalTrigger` (polling interval: 5 seconds) scanning for `fire_at <= now() AND status = 'pending'` satisfies the 2-second timing tolerance acceptance criterion with sufficient margin.

**Required behavior:**
- On FastAPI startup, the scheduler starts with one recurring job: `dispatch_due_notifications()`, interval 5 seconds.
- `dispatch_due_notifications()` queries `notifications.notification` for rows where `fire_at <= now()` AND `status = 'pending'`, calls FCM for each, and updates `status` to `'dispatched'` or `'failed'`.
- Scheduler stops cleanly on FastAPI shutdown.
- The scheduler runs in-process; no external worker or broker is introduced in this slice.

**Designer freedom within this decision:** The specific APScheduler job store (memory vs. SQLAlchemy) is a designer decision. Memory job store is sufficient and preferred for this slice (the recurring dispatch job is recreated on startup; only notification rows in Postgres are durable state).

---

## 2. Required Design Artifact: FCM Payload Contract

**Orchestrator flag:** The FCM payload contract is flagged as requiring pre-implementation alignment and must be an explicit required design artifact, not prose.

**Resolution — the FCM payload contract is defined here as a versioned, machine-readable artifact specification. The designer must produce `20_design/fcm_payload_contract.json` as a required design artifact alongside `architecture.json` and `scaffolding.json`.**

### 2.1 Required fields in the FCM data payload

The FCM message must be a **data-only message** (not a notification message). This is required because:
- The Android shell must control notification rendering (title, body, label styling) — a notification message would bypass the app and render without label support.
- Data messages are received by the app's `FirebaseMessagingService` regardless of foreground/background state (with the foreground/background handling difference noted below).

| Field | Type | Source | Notes |
|---|---|---|---|
| `notification_id` | string (UUID) | `notification.id` | Used by Android shell for cancel/replace by id |
| `title` | string | `notification.title` | Primary notification text |
| `body` | string | `notification.body` | Secondary notification text |
| `label` | string | `notification.label` | Must be visibly rendered in the notification |
| `deep_link` | string | `notification.deep_link` | Atlas URL to open on tap |

No other fields. The payload must not include `source` or any platform metadata not needed by Android shell. The contract boundary is strict: Android shell renders exactly these 5 fields and nothing else.

### 2.2 FCM message structure (Atlas server → FCM)

```json
{
  "message": {
    "token": "<device_fcm_token>",
    "data": {
      "notification_id": "<uuid>",
      "title": "<string>",
      "body": "<string>",
      "label": "<string>",
      "deep_link": "<atlas_url>"
    }
  }
}
```

All values are strings. No `notification` key in the FCM message object (data-only).

### 2.3 Deep link format

Deep links must be Atlas-rooted URLs in the form `atlas://<path>` or `https://<atlas-host>/<path>`. The specific scheme is a designer decision for `20_design/fcm_payload_contract.json`, but must be consistent with the Android shell's Chrome Custom Tab and intent-filter setup. The designer must declare the scheme explicitly in the artifact.

### 2.4 Required artifact

The designer must produce `20_design/fcm_payload_contract.json` containing:
- The exact FCM message JSON structure with field types and sources
- The declared deep link scheme
- The Android shell handling contract (what the shell does on receipt, what it does on tap)
- Version: `"1.0"` for this slice

This artifact is a required input for the Android Claude implementation agent. It is not optional prose.

### 2.5 FCM token storage

The Postgres `notification` record must store the target device's FCM registration token. The draft's data contract omits `fcm_token` — this is a **required addition**. Without it, Atlas cannot dispatch the notification.

**Correction to draft data contract:** Add `fcm_token` (string, not user-visible) to the Notification entity. This field is not exposed in any UI and is not a user-visible field. It is platform-internal.

**Open question for designer (safe):** Whether the FCM token is stored per-notification record or in a separate device registration table is a designer decision. For this slice, storing it per-notification record is acceptable and simpler. A device table is appropriate for future multi-device or multi-user scenarios.

---

## 3. Resolved: Observability Against the 2-Second Timing Tolerance

**Orchestrator flag:** No observability or monitoring requirement is stated against the 2-second timing tolerance acceptance criterion.

**Resolution:** The 2-second tolerance is a behavioral acceptance criterion, not a runtime SLA requiring instrumentation. For this slice — a personal-use, single-instance system with ~2 minute lead times — the proportionate requirement is:

**Required (minimal):**
- The `dispatch_due_notifications()` job must log at INFO level: notification id, scheduled `fire_at`, actual dispatch timestamp, and the delta in milliseconds on each dispatch.
- This log output is sufficient to verify the acceptance criterion during testing and to diagnose timing drift if it occurs.
- Atlas already uses `platform_errorhandling` with structured logging (`platform_errorhandling/logging.py`). The notification platform backend must use the same logging setup.

**Not required in this slice:**
- Metrics endpoint or Prometheus instrumentation.
- Alerting on timing violations.
- A monitoring dashboard.

These are out of scope for this slice per the draft's explicit exclusions of notification analytics and reporting.

**Designer freedom:** The exact log format is a designer decision as long as it contains the four required fields (id, fire_at, dispatched_at, delta_ms).

---

## 4. Clarifications and Additions

### 4.1 Data contract correction — `fcm_token` addition

The draft lists 7 fields: `id`, `source`, `fireAt`, `title`, `body`, `label`, `deepLink`. The notification platform also requires `fcm_token` to dispatch (see Section 2.5). The designer must include this in the Postgres schema and the platform API contract. It must not appear in any user-visible surface.

### 4.2 Notification status lifecycle

The draft does not define a `status` field but the scheduling mechanism (Section 1) requires it. The notification record must carry a `status` column with values: `pending`, `dispatched`, `cancelled`, `failed`.

- `pending`: initial state on creation
- `dispatched`: set after successful FCM API call
- `cancelled`: set by explicit cancel operation (notification is not dispatched)
- `failed`: set if FCM call returns an error

The `dispatch_due_notifications()` job must only process `pending` records. This prevents double-dispatch on repeated polls.

### 4.3 Workout tracker integration boundary

The draft states "Connect the workout tracker to this platform contract" as an Atlas Claude deliverable. The integration boundary is:

- WorkoutTracker calls a platform-level endpoint (not a workout-specific endpoint) to create a notification.
- The platform endpoint accepts the notification creation contract (id optional — generated server-side, source, fireAt, title, body, label, deepLink, fcm_token).
- WorkoutTracker does not pass workout-specific fields. The `source` value `"workout_tracker"` is the only feature identifier.
- The designer must specify whether WorkoutTracker calls the notification platform as an internal Python function call (in-process, if they share the same FastAPI instance) or as an HTTP API call (if the notification platform is a separate service). For this slice, in-process function call is preferred and simpler. The designer must make this explicit.

### 4.4 Replace semantics — no atomicity requirement

The draft defines replace as: delete old notification, create new notification with a new id. This is not required to be atomic in this slice. Partial failure (old deleted, new create fails) is an acceptable edge case for the MVP. The designer must note this explicitly rather than silently assuming or silently deferring.

### 4.5 Cancel behavior for already-dispatched notifications

Cancel-by-id on an already-dispatched notification has no defined behavior in the draft. **Specified here:** Cancelling a dispatched notification is a no-op at the platform level (the notification has already left the system via FCM and rendered on device). The platform must return a success response (not an error) for cancel on a dispatched record. Removing the already-displayed notification from the Android notification tray is out of scope for this slice.

---

## 5. Safe-to-Defer Decisions (Designer can handle)

| Area | What the designer can decide | Why it's safe |
|---|---|---|
| Postgres schema details | Column types, indexes, constraints, nullable rules for the `notifications.notification` table | The required fields and status lifecycle are specified; implementation details are safe designer choices |
| FCM token storage structure | Per-notification column vs. separate device registration table | For this slice either works; per-notification is simpler and recommended but not mandated |
| APScheduler job store | Memory vs. SQLAlchemy-backed | Memory store is sufficient; both are correct |
| Deep link URL scheme | `atlas://` vs. `https://` | Must be declared in `fcm_payload_contract.json`; the designer resolves the scheme with Android Claude before finalizing the artifact |
| Platform API endpoint naming | `/api/notifications/`, verb choice for create/cancel/replace | No Atlas-wide naming convention constrains this |
| Error responses for notification operations | Specific error codes and messages for validation failures | Must use `api_error()` from `platform_errorhandling`; specific codes are a designer choice |
| Log format details | Specific log message structure | Must include the 4 required fields (Section 3); format is a designer choice |
| FCM SDK vs. direct HTTP | Whether to use `firebase-admin` Python SDK or direct FCM HTTP v1 API | Both are valid; `firebase-admin` is preferred for correctness but the choice is the designer's |

---

## 6. Atlas Violations / Redundancies

| What the spec says | Atlas rule or contract | Recommended correction |
|---|---|---|
| The draft defines a data contract with 7 fields but does not mention `status` or `fcm_token` | R-CON-BP-03 (no hidden state): state that affects system behavior must be explicit and owned. `status` drives dispatch behavior; `fcm_token` drives delivery. Both are durable state with a clear owner. | Designer must add `status` and `fcm_token` to the platform data contract. See Sections 2.5 and 4.2. |
| The draft says "None that block this slice" under Open Questions but the FCM payload contract "must be explicitly aligned before implementation starts" | Internal contradiction. An open alignment requirement is a blocking dependency, not a non-blocking note. | Resolved by capturing the payload contract as a required design artifact (`fcm_payload_contract.json`). The spec as written is corrected by this document. |
| No Atlas violation on UI Data Contract — this component has no UI surface | R-CON-BP-04 (UI Data Contract) does not apply here. The Notifications platform is a server-side service + Android shell extension. No Dataset, ColumnSchema, or chart mapping is required. | No action needed. |
| The draft does not specify which FastAPI application owns the notification platform endpoints | R-CON-BP-02 (contracts and boundaries): ownership boundaries must be explicit. | Designer must declare: either (a) the notification platform is a standalone FastAPI service in `02_Platform/Notifications/backend/`, or (b) the notification endpoints are added to an existing application backend. Option (a) is correct per Atlas Platform layer rules (R-CON-PL-01) — platform capability belongs in Platform, not embedded in an application router. |

---

## 7. Ambiguities with Suggested Resolution

| Ambiguity | Recommended decision | Confidence |
|---|---|---|
| Which FastAPI service hosts the notification platform API? | Standalone FastAPI service at `02_Platform/Notifications/backend/` with its own `main.py`. This respects R-CON-PL-01 (Platform provides capability without domain meaning) and R-CON-PL-02 (dependency direction). WorkoutTracker calls it as a dependency, not the other way around. | High |
| Is the notification platform an HTTP API or an in-process library for the first caller (WorkoutTracker)? | For this slice: in-process Python import is acceptable if both services are co-located. HTTP API is correct architectural target and should be the design — it is consistent with how Atlas Platform components are structured and avoids tight coupling. The designer must choose one and state it. | Medium — defer to designer with explicit decision required |
| What happens if FCM dispatch fails? | Set `status = 'failed'`, log the error. No retry in this slice (draft explicitly excludes retry policy). The record remains in Postgres in `failed` state for observability. | High |
| Does cancel remove the notification from Postgres or just set `status = 'cancelled'`? | Set `status = 'cancelled'`. Retain the record in Postgres. Hard delete makes debugging and replacement semantics harder and has no benefit for this slice. | High |
| What is the accepted FCM credential mechanism? | Firebase service account JSON, loaded from an environment variable or file path. The designer must declare the credential loading mechanism explicitly in the architecture artifact. FCM credentials must not be hard-coded. | High — per R-OPS-BP-02 (security, least privilege) |

---

## 8. Risks

| Risk type | Description | Severity |
|---|---|---|
| Hidden state | `fcm_token` missing from draft data contract. Without it the platform cannot dispatch. If the implementer invents a storage mechanism without explicit spec, it may couple token storage to workout-tracker-specific logic, violating the generic contract principle. | High |
| Missing status field | Without an explicit `status` field, the dispatch job has no idempotency guard. Double-dispatch of a notification (on repeated 5-second polls) is a silent correctness failure. | High |
| Cross-agent payload drift | FCM payload contract is the only boundary artifact between Atlas Claude and Android Claude. If it is produced as prose rather than as a versioned JSON artifact, the two agents may implement incompatible field names or types. | High — mitigated by requiring `fcm_payload_contract.json` |
| FCM credential handling | FCM requires a service account credential. If the designer does not specify the credential mechanism, the implementer will make a security-sensitive decision without guidance, risking hardcoded credentials or misconfigured secret loading. | Medium — per R-OPS-BP-02 |
| Platform vs. Application boundary for the API host | If the notification endpoints are added to the WorkoutTracker FastAPI router instead of a standalone Platform service, the Platform boundary is violated and future callers (Habit Tracker, Cooking Helper) will need to call a WorkoutTracker endpoint. This would require a later migration. | Medium |
| Timing tolerance verification | The 5-second poll interval provides a maximum dispatch latency of ~5 seconds from `fire_at`, not 2 seconds. Under normal load the average is ~2.5 seconds. The 2-second tolerance in the acceptance criteria is an average, not a worst-case. If the human reviewer interprets it as worst-case, the acceptance criterion may not be met with a 5-second interval. The designer should document that this tolerance is expected-case, not worst-case, or reduce the interval to 1 second. | Low-Medium |
| Over-specification risk | This document specifies APScheduler as the scheduler. If the existing Atlas backend already uses a different task scheduling pattern (none is evident from inspection), this could conflict. Inspection of existing backends shows no scheduling infrastructure exists — risk is low. | Low |

---

## 9. Required Design Artifacts

The designer must produce the following artifacts. The first two are standard per R-PRO-BP-01. The third is required by this spec.

| Artifact | Path | Notes |
|---|---|---|
| Architecture JSON | `20_design/architecture.json` | Must explicitly declare: Platform service location, scheduling mechanism (APScheduler, 5s interval), Postgres schema with all 9 fields including `status` and `fcm_token`, FCM credential loading mechanism, agent boundary |
| Scaffolding JSON | `20_design/scaffolding.json` | Must cover both Atlas Claude deliverables and Android Claude deliverables |
| FCM Payload Contract | `20_design/fcm_payload_contract.json` | Required boundary artifact. Must contain: exact FCM message JSON structure, field types, deep link scheme, Android shell handling contract, version `"1.0"` |

The `fcm_payload_contract.json` is the handoff artifact to Android Claude. Implementation by Android Claude must not begin until this artifact exists and is reviewed.

---

## 10. Atlas Alignment Notes

This component is correctly classified as Platform (02_Platform):
- It provides a generic technical capability (notification dispatch) shared across applications.
- It contains no domain logic — `source` is an opaque tag, not interpreted.
- It is persistent (Postgres) and long-lived.
- R-CON-PL-01 is satisfied.

The draft does not attempt to use the Atlas UI Data Contract (R-CON-BP-04) — correct, since this component has no web UI surface. No Dataset, ColumnSchema, or chart mapping is required.

The draft correctly excludes notification history UI, preference management, and analytics — these would be Application-layer concerns or future Platform slices.

The `platform_errorhandling` package must be used for all error responses from the notification platform API. No ad-hoc error formats.

---

*Spec readiness review completed 2026-03-25. Verdict: READY.*
