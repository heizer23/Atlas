# CalendarConnector – Implementation Status

## 1. Purpose

CalendarConnector provides Google Calendar OAuth connection management, token persistence, and read-only calendar event retrieval as a reusable platform capability. It allows any Atlas application to initiate a Google Calendar consent flow, persist the resulting connection and token state, and retrieve normalized calendar events for a given time window — without coupling those operations to Atlas login state or to any application's domain logic.

## 2. Current Concept

The component models a system-scoped (one per Atlas instance) Google Calendar connection. Connection state and token state are stored in separate tables. A short-lived DB nonce table guards the OAuth callback against CSRF. All data-returning endpoints return a `Dataset` per R-CON-BP-04. Token values are internal-only and never surfaced in API responses. The component treats Atlas as a single-tenant system: no per-user identity exists at this layer.

## 3. Current Capabilities

- Initiates a Google OAuth 2.0 consent flow for `calendar.readonly` scope, generating and persisting a CSRF nonce, and redirecting the browser to Google's authorization endpoint.
- Receives the OAuth callback from Google, validates and deletes the CSRF nonce (one-time use), exchanges the authorization code for access and refresh tokens, fetches the connected account email via the Google userinfo endpoint, and persists connection and token state to Postgres.
- Retrieves calendar events from the connected Google Calendar for a caller-supplied ISO8601 time window. Performs lazy token refresh if the access token is expired. Normalizes Google Calendar API v3 event items into a `Dataset` with `object_type=calendar_event`.
- Returns a connection health `Dataset` with `object_type=calendar_connection`. Returns a single `not_connected` row when no connection exists; never returns an error for an absent connection.
- Runs idempotent schema initialization (`migrations/001_init.sql`) on service startup via `database.py init_schema()`.
- Updates connection status (`expired`, `revoked`, `error`) and records `last_success_at` timestamps on the `calendar_connection` row as token lifecycle events occur.

## 4. Current Data Model

**calendar_connection**
Key fields: `id` (serial PK), `provider` (text, `"google"`), `account_email` (text, nullable), `status` (text: `connected|expired|revoked|error`), `granted_scopes` (text), `created_at`, `updated_at` (timestamptz), `last_success_at` (timestamptz, nullable), `last_error` (text, nullable).
Purpose: Singleton row representing the current Google Calendar authorization for this Atlas instance. No `user_id` FK.

**calendar_token**
Key fields: `id` (serial PK), `connection_id` (integer FK → `calendar_connection.id`, UNIQUE), `access_token` (text, plaintext), `refresh_token` (text, nullable, plaintext), `token_expiry` (timestamptz), `token_type` (text, nullable), `scope` (text, nullable), `created_at`, `updated_at` (timestamptz).
Purpose: Stores the live OAuth tokens for the calendar connection. One row per connection. Internally accessed only; token values never returned in API responses.

**calendar_oauth_state**
Key fields: `id` (serial PK), `nonce` (text, UNIQUE), `expires_at` (timestamptz), `created_at` (timestamptz).
Purpose: Short-lived CSRF state nonces for in-flight OAuth connect flows. Each nonce is deleted on first use in the callback. TTL is 10 minutes.

## 5. Contracts Consumed

- `platform_contracts.Dataset`, `DatasetMeta`, `ColumnSchema` from `02_Platform/packages/platform_contracts/contracts.py` — used by both data-returning endpoints.
- `platform_errorhandling.api_error()` from `02_Platform/packages/platform_errorhandling/api_response.py` — used for all error responses.
- `platform_errorhandling.install_exception_handlers()`, `install_request_timing()`, `setup_logging()` from `02_Platform/packages/platform_errorhandling` — installed in `main.py`.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from `01_System/config.env` / `01_System/secrets.env` — read as `GoogleAuth_ClientID` / `GoogleAuth_Secret` with fallback to `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`. Reuses the existing Atlas OAuth client; no separate client registered.
- `CALENDAR_CONNECTOR_PORT` from `01_System/config.env` — value `8021`, used by `compose.yml` and the callback URI builder.
- Atlas shared Postgres database (`02_Platform/01_Postgres`) — `calendar_connection`, `calendar_token`, `calendar_oauth_state` tables.
- Google OAuth 2.0 authorization endpoint (`https://accounts.google.com/o/oauth2/v2/auth`) and token endpoint (`https://oauth2.googleapis.com/token`) — external.
- Google Calendar API v3 events.list (`https://www.googleapis.com/calendar/v3/calendars/primary/events`) — external.
- Google userinfo endpoint (`https://www.googleapis.com/oauth2/v3/userinfo`) — external, used to resolve account email after token exchange.

## 6. Interfaces Exposed

### 6.1 API Endpoints

**GET /api/calendar/google/connect/start**
Purpose: Initiates Google Calendar OAuth consent flow.
Input: None.
Output: `302 RedirectResponse` to Google authorization URL with `scope=calendar.readonly`, `access_type=offline`, `prompt=consent`, and a CSRF state nonce. Nonce row inserted in `calendar_oauth_state`.

**GET /api/calendar/google/connect/callback**
Purpose: Receives OAuth authorization code from Google, validates CSRF nonce, exchanges code for tokens, persists connection and token state.
Input: Query params `code` (str), `state` (str); optional `error` (str) if Google returned a denial.
Output: `200 JSONResponse` with `{status, account_email, message}` on success. `api_error` (OAUTH_DENIED, OAUTH_STATE_MISMATCH, or GOOGLE_API_ERROR) on failure.

**GET /api/calendar/events**
Purpose: Returns normalized calendar events for a time window.
Input: Query params `from` (ISO8601 datetime str), `to` (ISO8601 datetime str).
Output: `Dataset` (R-CON-BP-04) with `object_type=calendar_event`. Row shape: `CalendarEventRow` — fields `id`, `title`, `description`, `start_at`, `end_at`, `all_day`, `location`, `status`, `source_calendar_id`, `source_calendar_label`. `api_error` on NO_CALENDAR_CONNECTION (404), CALENDAR_TOKEN_EXPIRED (503), CALENDAR_ACCESS_REVOKED (503), or GOOGLE_API_ERROR (502).

**GET /api/calendar/status**
Purpose: Returns current calendar connection health. Never returns an error response for an absent connection.
Input: None.
Output: `Dataset` (R-CON-BP-04) with `object_type=calendar_connection`. Single row shape: `CalendarConnectionStatusRow` — fields `id` (fixed `"system"`), `provider`, `account_email`, `status`, `granted_scopes`, `last_success_at`, `last_error`, `created_at`, `updated_at`. Returns `status=not_connected` row if no connection record exists.

### 6.2 UI Datasets

CalendarEventRow dataset: served by `GET /api/calendar/events`. Schema keys: `id`, `title`, `start_at`, `end_at`, `all_day`, `status`, `location`, `description`, `source_calendar_id`, `source_calendar_label`. Contract: R-CON-BP-04.

CalendarConnectionStatusRow dataset: served by `GET /api/calendar/status`. Schema keys: `id`, `provider`, `account_email`, `status`, `granted_scopes`, `last_success_at`, `last_error`, `created_at`, `updated_at`. Contract: R-CON-BP-04.

### 6.3 Events Emitted

None identified.

### 6.4 Events Consumed

None identified.

### 6.5 External / Platform Dependencies

- `02_Platform/packages/platform_contracts` — Dataset contract types.
- `02_Platform/packages/platform_errorhandling` — Error envelope, exception handlers, request timing, logging.
- `02_Platform/01_Postgres` — Shared Postgres database.
- `02_Platform/02_Atlas_Shell/nginx.conf` — Proxy block routing `/api/calendar` to `atlas-calendar-connector:8000`.
- Google OAuth 2.0 and Google Calendar API v3 — external provider services.

## 7. Known Gaps

### 7.1 Implementation Gaps

**connect_callback non-atomic writes:** `upsert_connection()` and `upsert_token()` are called within the same `get_db()` context block in `connect_callback`, but each function calls `conn.commit()` internally. The two writes are not wrapped in a single database transaction. If `upsert_token()` fails after `upsert_connection()` succeeds, the system will have a `calendar_connection` row with `status='connected'` and no corresponding `calendar_token` row. `GET /api/calendar/events` will return `NO_CALENDAR_CONNECTION` while `GET /api/calendar/status` returns `status='connected'` — an inconsistent visible state. Recovery requires re-running the OAuth flow.

**Automated tests not implemented:** All three test files (`tests/test_connect_flow.py`, `tests/test_events.py`, `tests/test_status.py`) contain only docstring stubs. The test scenarios defined in `architecture.json` `deferrals.test_writer` have not been implemented. End-to-end correctness has been verified by human testing only.

**token_refresh_check not isolated as a service function:** `architecture.json` `internal_flow` step 3 describes `token_refresh_check` as a named internal operation. It is implemented inline within `get_events` in `routers/calendar.py` rather than as a discrete function in a service module. This reduces unit testability of the refresh path.

### 7.2 Inconsistencies

**all_day ColumnSchema type vs. row value type:** The `ColumnSchema` for `all_day` in the events Dataset uses `type="boolean"`, but the row value is a Python string `"true"` or `"false"` (declared as `str` in `CalendarEventRow`). The architecture document specifies `all_day` as a string field to satisfy `ColumnType` rules, while the `ColumnSchema` declares it as `"boolean"`. These two declarations are internally inconsistent. Frontend behavior depends on how the UI platform primitive handles a `boolean` schema key with a string row value.

### 7.3 Conformance Issues

No confirmed mismatches with explicit design artifacts beyond those recorded in 7.1 and 7.2.

### 7.4 Missing or Ambiguous Design Baseline

**Plaintext token storage (known, documented deferral):** `access_token` and `refresh_token` are stored as plaintext `TEXT` columns in `calendar_token`. This is explicitly classified as a known security gap in `architecture.json` risks and `migrations/001_init.sql`. Documented in `implementation_notes.md`. Must be addressed before production use via application-level encryption or `pgcrypto`.

**Google Cloud Console callback URI registration (deployment pre-condition):** The URI `http://localhost:8021/api/calendar/google/connect/callback` must be registered as an authorized redirect URI in Google Cloud Console before the OAuth flow can succeed. This is documented as a deployment pre-condition in `implementation_notes.md`. It is not a code defect.

**migrate.py does not cover Platform paths:** The global `migrate.py` scans only `03_Application/*/migrations/`. Schema deployment for `CalendarConnector` is handled exclusively by `database.py init_schema()` on service startup. Extension of `migrate.py` to cover Platform paths is deferred per `architecture.json` `design_decisions`.

## 8. Non-Scope

- Writing events to Google Calendar.
- Creating or managing Atlas-specific target calendars.
- Background sync workers or recurring sync jobs.
- Webhook push notification subscriptions.
- Multi-provider calendar abstraction.
- Per-user or multi-user connections — Atlas is system-scoped; one connection per instance.
- Chronos-specific business logic or task-to-event mapping.
- At-rest token encryption (deferred gap).
- Frontend UI components.
- Extension of global `migrate.py` to scan Platform paths.

## 9. Recommendation

### Recommended Owner

Implementer

### Reason

The sprint is functionally complete and end-to-end human-verified. Two follow-up items require implementation work: wrapping the two callback DB writes in a single transaction (correctness risk), and implementing the test suite stubs (test coverage gap). The `all_day` type inconsistency should be clarified and resolved by the implementer.

### Suggested Next Action

1. Fix `connect_callback` atomicity: remove the internal `conn.commit()` calls from `upsert_connection()` and `upsert_token()` when called in sequence within `connect_callback`, and commit once after both writes succeed.
2. Implement `tests/test_connect_flow.py`, `tests/test_events.py`, `tests/test_status.py` per the scenarios defined in `architecture.json` `deferrals.test_writer`.
3. Resolve the `all_day` ColumnSchema type: change the schema declaration to `type="string"` to match the row value type, or change `CalendarEventRow.all_day` to a boolean and serialize it accordingly.

### Priority

Medium

---

## Validation Warnings

- **connect_callback non-atomic writes:** `upsert_connection()` and `upsert_token()` each call `conn.commit()` independently within a single `get_db()` block. Partial write state is possible if the second call fails. This is an implementation-level correctness risk not explicitly mandated by a design artifact, but observable from the code.
- **Automated tests not implemented:** Test files contain only stubs. Architecture artifact (`architecture.json` `deferrals.test_writer`) defines specific test scenarios that are unexecuted. Human verification covers end-to-end flow only.
- **all_day ColumnSchema type mismatch:** Schema declares `type="boolean"` but `CalendarEventRow.all_day` is `str`. Frontend rendering behavior for this column is undefined.
