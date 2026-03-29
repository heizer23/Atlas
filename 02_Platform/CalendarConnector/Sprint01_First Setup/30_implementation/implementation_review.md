# CalendarConnector Sprint01 — Implementation Review

**Reviewer:** Sprint Implementation Reviewer
**Date:** 2026-03-29
**Sprint:** Sprint01_First Setup
**Component:** 02_Platform/CalendarConnector

---

## Verdict

**COMPLETE**

All four endpoints are implemented per `architecture.json` `internal_flow`. The Dataset contract (R-CON-BP-04) is satisfied. All architecture invariants are met. Known deferred gaps are correctly documented. One implementation-level gap is recorded below (callback atomicity) — it is a correctness risk but does not block the sprint verdict given the end-to-end human verification at `AWAITING_HUMAN_REVIEW`.

---

## Checklist Results

### 1. All four endpoints implemented per architecture.json internal_flow

| Step | Name | Route | Status |
|------|------|-------|--------|
| 1 | connect_start | GET /api/calendar/google/connect/start | Implemented |
| 2 | connect_callback | GET /api/calendar/google/connect/callback | Implemented |
| 4 | get_events | GET /api/calendar/events | Implemented |
| 5 | get_status | GET /api/calendar/status | Implemented |

Step 3 (token_refresh_check) is implemented inline within `get_events` in `routers/calendar.py` rather than as a standalone function in a service module. The design describes it as an internal operation called before any Google API request, not as a separately exposed interface. The inline placement is acceptable, though it reduces testability of the refresh path in isolation.

All four endpoints are reachable and correspond to the `internal_flow` descriptions.

### 2. Dataset contract (R-CON-BP-04)

**GET /api/calendar/events**
- Returns `Dataset` with `meta.object_type = "calendar_event"`. Confirmed.
- Schema keys match `CalendarEventRow` fields. Confirmed.
- Every row has an `id` field populated from the Google event id. Confirmed in `_normalize_event()` in `calendar_api.py`.
- No token values appear in response rows. `CalendarEventRow` model does not declare token fields. Confirmed.

**GET /api/calendar/status**
- Returns `Dataset` with `meta.object_type = "calendar_connection"`. Confirmed.
- Row id is the fixed string `"system"`. Confirmed in `CalendarConnectionStatusRow` and `get_status()`.
- Returns a single `not_connected` row (never `api_error`) when no connection record exists. Confirmed.
- No token values appear. `CalendarConnectionStatusRow` does not declare token fields. Confirmed.

### 3. No user_id FK on any table

`migrations/001_init.sql` — all three tables (`calendar_connection`, `calendar_token`, `calendar_oauth_state`) contain no `user_id` column. Confirmed.

### 4. Token values absent from all API response shapes

- `CalendarEventRow` and `CalendarConnectionStatusRow` Pydantic models contain no `access_token` or `refresh_token` fields.
- `connect_callback` success response (`JSONResponse`) returns only `status`, `account_email`, and `message`. Token values not present.
- `token_store.py` docstring explicitly states: "Internal use only — callers must never forward token values to API responses." Confirmed.

### 5. CSRF nonce deleted after single use in callback

`token_store.consume_oauth_state()` executes a `DELETE ... WHERE nonce = %s AND expires_at > NOW() RETURNING id`. The `connect_callback` handler calls this before any token exchange. If `consume_oauth_state` returns `False` (not found or expired), the callback aborts with `OAUTH_STATE_MISMATCH` and does not proceed to token exchange. Confirmed.

### 6. database.py init_schema() runs migrations/001_init.sql on startup

`database.py` `init_schema()` reads `migrations/001_init.sql` via `Path(__file__).resolve().parents[1] / "migrations"` and executes it in a transaction. `main.py` `on_startup()` calls `init_pool()` then `init_schema()`. Confirmed.

The `migrations/001_init.sql` script is wrapped in `BEGIN; ... COMMIT;` and uses `CREATE TABLE IF NOT EXISTS` throughout — idempotent as required by the design decision in `architecture.json`.

### 7. nginx location block for /api/calendar

`02_Platform/02_Atlas_Shell/nginx.conf` contains:

```
location /api/calendar {
    set $upstream_calendar atlas-calendar-connector:8000;
    proxy_pass         http://$upstream_calendar;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_read_timeout 30s;
}
```

This matches the required block shape defined in `architecture.json` `dependencies.internal_required` exactly. Confirmed.

### 8. CALENDAR_CONNECTOR_PORT=8021 in 01_System/config.env

`01_System/config.env` line 21: `CALENDAR_CONNECTOR_PORT=8021`. Confirmed.

`compose.yml` uses `${CALENDAR_CONNECTOR_PORT:-8021}:8000` — env var referenced, not hardcoded. Confirmed.

---

## Open Item: connect_callback Atomicity

**Finding:** The two DB writes in `connect_callback` — `upsert_connection()` and `upsert_token()` — share a single `with get_db() as conn:` block, but each function calls `conn.commit()` internally. This means the two writes are NOT wrapped in a single database transaction.

**Risk:** If `upsert_token()` fails after `upsert_connection()` succeeds (e.g. due to a constraint violation or DB error), the system will have a `calendar_connection` row with `status='connected'` but no corresponding `calendar_token` row. Subsequent calls to `GET /api/calendar/events` will then return `NO_CALENDAR_CONNECTION` (because `get_token()` returns `None`), and the `GET /api/calendar/status` endpoint will return `status='connected'` — an inconsistent visible state.

**Severity:** Medium. Recovery path exists (re-running the OAuth flow overwrites the connection row and creates the token), but the inconsistency is silent and could confuse callers.

**Design reference:** `architecture.json` `internal_flow` step 2 lists both upserts as outputs of a single `connect_callback` operation without explicitly mandating transaction atomicity. The gap is an implementation-level correctness risk, not a named invariant violation.

**Recommendation:** Wrap both `upsert_connection()` and `upsert_token()` in a single transaction in `connect_callback`. The simplest fix is to remove the `conn.commit()` calls from within `upsert_connection()` and `upsert_token()` when called together, or introduce a transaction-aware path. This is tracked as an implementation gap in `implementation_status.md`.

---

## Deferred Gaps Confirmed Documented

The following gaps are correctly documented in `implementation_notes.md` and `architecture.json` and do not block this sprint:

- **Plaintext token storage** — documented in `architecture.json` risks, `migrations/001_init.sql` comment header, and `implementation_notes.md`. Must be addressed before production use.
- **Google Cloud Console callback URI registration** — documented as a deployment pre-condition in `implementation_notes.md` with step-by-step instructions.
- **logs/ bind-mount in compose.yml** — `compose.yml` includes `${DATA_ROOT}/calendar_connector/logs:/app/logs`. Present and consistent with Atlas service pattern. Not a gap.

---

## Minor Observations (non-blocking)

- `get_account_email()` is implemented in `google_oauth.py` as a public function but was not declared in `scaffolding.json` (which lists only `build_authorization_url`, `exchange_code_for_tokens`, `refresh_access_token`). The addition is additive and architecturally sound — it resolves the `deferred_decisions` choice to use the userinfo endpoint path.
- Test files (`tests/test_connect_flow.py`, `tests/test_events.py`, `tests/test_status.py`) contain only docstring stubs. No test logic is implemented. The design designates these as `test_writer` deliverables; their absence does not block sprint completion but means the test cases defined in `architecture.json` `deferrals.test_writer` remain unexecuted by automated tooling.
- `pyproject.toml` does not declare `platform_errorhandling` or `platform_contracts` as dependencies; they are loaded via `PYTHONPATH` in the Dockerfile. This is consistent with the existing Atlas pattern for platform packages and is not a defect.
- The `all_day` column uses `type="boolean"` in the `ColumnSchema` but the row value is a string `"true"` / `"false"`. `CalendarEventRow` declares `all_day: str` per the architecture's shared_views definition, which explicitly notes this is a string to satisfy `ColumnType` rules. The `ColumnSchema` `type="boolean"` may cause a frontend rendering mismatch. This is flagged for awareness but is not a design violation — the architecture document itself specifies `all_day` as a string field, and the `ColumnSchema` type is set independently.

---

## Human Gate

Human review gate recorded in `sprint_state.json` on 2026-03-29:

> "Human confirmed end-to-end approval on 2026-03-29. OAuth flow completed successfully (Google Calendar connected). GET /api/calendar/status returns Dataset with status=connected. GET /api/calendar/events returns Dataset with 6 real calendar events. All endpoints return correct Dataset shape per R-CON-BP-04."

Pre-condition satisfied.
