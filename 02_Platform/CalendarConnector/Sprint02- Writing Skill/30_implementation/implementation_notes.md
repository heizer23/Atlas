# CalendarConnector Sprint02-Writing Skill — Implementation Notes

**Implementer:** sprint_implement (platform implementer)
**Date:** 2026-04-05
**Sprint:** Sprint02-Writing Skill
**Component:** 02_Platform/CalendarConnector

---

## Summary of Changes

This sprint extends CalendarConnector from read-only to write-capable. Seven files changed, two files added. No breaking changes to existing endpoints.

---

## Files Changed

### `app/database.py`
- `init_schema()` updated: previously hardcoded to execute only `001_init.sql`. Now scans all `.sql` files in `migrations/` sorted by filename, executing each in its own transaction. This ensures `002_write_capability.sql` and any future migrations run automatically on startup.

### `app/services/google_oauth.py`
- `_CALENDAR_SCOPE` constant updated from `calendar.readonly` to `calendar` (read+write superset).
- No other changes to this file.

### `app/models.py`
- Added `CalendarCreateEventRequest` Pydantic model: `title` (required), `start_at` (required), `end_at` (required), `description` (optional), `location` (optional), `all_day` (optional bool, default False).
- Added `CalendarCreateEventResult` Pydantic model: success response shape for POST /api/calendar/events. `all_day` is native `bool` (not string — this is not a Dataset row).

### `app/services/calendar_api.py`
- Added `create_event(access_token, target_calendar_id, request)` function.
- If `all_day=True`: uses date-only format (`{"date": "YYYY-MM-DD"}`) in Google API call.
- If `all_day=False`: uses dateTime format with RFC3339 timezone suffix.
- Raises `ValueError` on non-2xx response from Google.
- Existing `fetch_events()` unchanged.

### `app/services/token_store.py`
- Added `write_decision_log()` function. Inserts into `calendar_decision_log`. Commits immediately.
- Callers must wrap in `try/except` for best-effort semantics (documented in docstring).
- All existing functions unchanged.

### `app/routers/calendar.py`
- Added `_validate_target_calendar_id()`: called at startup, raises `RuntimeError` if env var absent.
- Added `_target_calendar_id()`: returns the env var value per-request.
- Added `_has_write_scope(granted_scopes)`: checks that `https://www.googleapis.com/auth/calendar` appears as a discrete token in the space-separated granted_scopes string (not just as a substring, which would incorrectly match `calendar.readonly`).
- Added `_WRITE_SCOPE` constant.
- Added `POST /api/calendar/events` endpoint.
- All existing endpoints unchanged.

### `app/main.py`
- Added call to `_validate_target_calendar_id()` in `on_startup()`. Service will not start if `CALENDAR_TARGET_CALENDAR_ID` is absent.
- Changed the `except` block to re-raise after logging, so startup failures are clearly fatal.

---

## Files Added

### `migrations/002_write_capability.sql`
- Adds `calendar_decision_log` table. `CREATE TABLE IF NOT EXISTS` — idempotent. Wrapped in `BEGIN/COMMIT`.

### `01_System/config.env` (modified, not new)
- Added `CALENDAR_TARGET_CALENDAR_ID=` with instructional comment. **Value is blank — operator must supply the Chronos calendar ID before deployment.**

---

## Deployment Pre-conditions (Required Before Deployment)

1. **CALENDAR_TARGET_CALENDAR_ID**: Set this value in `01_System/config.env` to the Google Calendar ID of the dedicated Chronos calendar. Retrieve it from Google Calendar settings (Settings > [Chronos calendar] > Integrate calendar > Calendar ID). Example format: `abc123@group.calendar.google.com`.

2. **Re-consent OAuth flow**: After deployment, the operator must visit `GET /api/calendar/google/connect/start` and complete the Google consent screen. This upgrades the stored grant from `calendar.readonly` to `calendar` (read+write). Until this is done, `POST /api/calendar/events` will return `INSUFFICIENT_SCOPE`.

3. **Google Cloud Console callback URI registration**: No change from Sprint01. The callback URI `http://localhost:8021/api/calendar/google/connect/callback` must remain registered.

---

## Known Gaps and Limitations

### Carried forward from Sprint01 (unchanged)
- **Plaintext token storage**: `access_token` and `refresh_token` stored as plaintext in Postgres. Must be addressed before production use.
- **connect_callback atomicity**: `upsert_connection()` and `upsert_token()` are not in a single transaction. Pre-existing gap, not made worse by this sprint.

### New in Sprint02
- **Blank CALENDAR_TARGET_CALENDAR_ID in config.env**: The value is intentionally blank in the committed file. The actual calendar ID is operator-supplied and must not be committed to git (it may contain a user-identifiable calendar identifier). Consider moving this to `secrets.env` if privacy is a concern.
- **FastAPI 422 validation errors**: Missing required fields in POST body return FastAPI's default 422 response (detail array), not an `api_error()` envelope. This is consistent with existing Atlas service behavior but is a known inconsistency.
- **Decision log not tested**: Test stubs exist in `tests/` but contain no implementation (carried forward from Sprint01). Decision log correctness is verified by end-to-end testing only.

---

## Implementation Decisions

### Scope check using token split vs. substring
`_has_write_scope()` splits `granted_scopes` on spaces and checks for exact membership of `_WRITE_SCOPE`. This correctly distinguishes:
- `calendar.readonly` scope (does not include the write scope string)
- `calendar` scope (write-capable)

A substring check (e.g., `_WRITE_SCOPE in granted_scopes`) would also work because `https://www.googleapis.com/auth/calendar` is NOT a substring of `https://www.googleapis.com/auth/calendar.readonly` (the `.readonly` suffix changes the string). However, the token-based check is more robust against unexpected scope string formats and is used here.

### Decision log `requested_at` field
Captured as `datetime.now(timezone.utc).isoformat()` at the start of the endpoint handler, before any async or network operation. This timestamps the intent, not the Google API completion time.

### Token refresh in create_event
The token refresh logic is duplicated from `get_events` rather than extracted into a shared helper. This is consistent with Sprint01 design, where `token_refresh_check` is described as an inline operation, not a separate service function. Extracting it is a refactor opportunity for a future sprint.
