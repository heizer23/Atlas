# Sprint03 Implementation Notes
## CalendarConnector — Edit and Delete

### Files Modified

**`app/models.py`**
- Added `atlas_event_id: str` (required) to `CalendarCreateEventRequest`.
- Renamed `CalendarCreateEventResult` to `CalendarEventOperationResult`. Status field changed from `str = "created"` to `Literal["created", "existing", "updated"]`. Added `atlas_event_id: str` field.
- `CalendarCreateEventResult` retained as a module-level alias pointing to `CalendarEventOperationResult` so any existing Sprint02 import references continue to resolve without error.
- Added `CalendarUpdateEventRequest` — all fields optional, at least-one enforcement done in the handler.
- Added `CalendarDeleteResult` — `status: Literal["deleted"]`, `atlas_event_id: str`, `google_event_id: Optional[str]`.

**`app/services/calendar_api.py`**
- Extracted `_rfc3339()` as a module-level function (was a nested function duplicated in two places).
- Retrofitted `create_event()` to include `extendedProperties.private.atlas_event_id` in the Google event body. Return type updated to `CalendarEventOperationResult`.
- Added `GoogleEventNotFoundError(ValueError)` — a distinct subclass so the router can distinguish a missing event (HTTP 404 from Google on PATCH) from other API failures without string-matching.
- Added `update_event()` — sends `extendedProperties.private.atlas_event_id` on every patch body to preserve metadata. Raises `GoogleEventNotFoundError` on 404, `ValueError` on other non-2xx.
- Added `delete_event()` — returns `True` on 204, `False` on 404, raises `ValueError` on other non-2xx. Uses the same `_EVENTS_PATCH_URL` template (calendar/{id}/events/{event_id}) with `httpx.delete`.

**`app/services/token_store.py`**
- Extended `write_decision_log()` signature with `atlas_event_id: Optional[str] = None`. The INSERT now includes the `atlas_event_id` column (added by migration 004). All Sprint02 call sites pass `None` implicitly.
- Added `get_event_index_by_atlas_id()` — returns any-status row (callers check `status` field).
- Added `upsert_event_index()` — uses `ON CONFLICT (atlas_event_id) DO UPDATE` to insert or reactivate in a single atomic statement.
- Added `mark_event_index_deleted()` — sets `status='deleted'`, writes optional note to `last_error`.
- Added `mark_event_index_error()` — sets `status='error'`, writes `error_summary` to `last_error`.

**`app/routers/calendar.py`**
- Updated module docstring to reflect 7 endpoints.
- Added import for `CalendarDeleteResult`, `CalendarEventOperationResult`, `CalendarUpdateEventRequest`, and `GoogleEventNotFoundError`.
- Extracted `_get_valid_access_token(conn, connection, token) -> str | JSONResponse` helper. Contains the ~40-line token expiry / refresh block that was duplicated. Returns a `str` (valid access token) on success or a `JSONResponse` (api_error) on failure. Every call site uses `isinstance(result, JSONResponse)` to branch.
- Added `_check_connection_and_scope(conn) -> tuple[dict, dict] | JSONResponse` — a second small helper that fetches connection + token rows and validates write scope. Used by all three write handlers to avoid another block of duplication.
- Refactored `get_events()` to use `_get_valid_access_token()`. Behavior is identical.
- Retrofitted `create_event()` for idempotent behavior:
  - Queries event index before calling Google.
  - Active mapping found: returns `status='existing'` (HTTP 200) without calling Google.
  - No active mapping: calls Google, writes index, returns `status='created'` (HTTP 201).
  - Index write failure after successful Google create: returns `INDEX_WRITE_FAILURE` (HTTP 500) — hard error, not silent.
  - All branches write a decision log entry (best-effort).
- Added `update_event()` handler for `PATCH /calendar/events/{atlas_event_id}`.
- Added `delete_event()` handler for `DELETE /calendar/events/{atlas_event_id}`.

### Invariants Verified

- `atlas_event_id` is never accepted in any request as a calendar target — only as event identity.
- All writes target `CALENDAR_TARGET_CALENDAR_ID` exclusively.
- `_get_valid_access_token` is called inside the `with get_db() as conn:` block so that any token upsert from a refresh is committed before the network call.
- `GoogleEventNotFoundError` is a `ValueError` subclass — handlers catch it before the broader `ValueError` catch.
- Index write failure after successful Google create is a hard error (INDEX_WRITE_FAILURE 500), consistent with draft §159.
- Decision log writes for update and delete remain best-effort (wrapped in try/except), consistent with Sprint02 pattern.
- Deleted index rows are never removed — `mark_event_index_deleted` always sets status, never DELETEs the row.

### Design Decisions

**`upsert_event_index` reactivation strategy**: chose reactivation (ON CONFLICT DO UPDATE) rather than inserting a new row. This is simpler and matches the architecture's deferred decision note. History is preserved through the `updated_at` and `last_success_at` timestamps.

**`_check_connection_and_scope` helper**: the architecture specified only `_get_valid_access_token` as a required helper. The write scope check was a 12-line block also duplicated across write handlers. Extracted to a second private helper to keep each handler small and readable. This is not a design gap — it is a local implementation choice within the allowed boundaries.

**`delete_event` and error-status index rows**: the architecture specifies that an active mapping is required for update, but the delete handler treats both `active` and `error` status rows as resolvable for deletion (attempts the remote delete). This is conservative: if the index is in error state, the Google event may or may not exist, and attempting a delete (which is idempotent by 404) is safe.

### Migrations

- `003_event_index.sql` and `004_decision_log_atlas_event_id.sql` were already present in `migrations/`. Not recreated.
- Both migrations must be run against the Postgres instance before Sprint03 endpoints are used.

### No Design Gaps

All items in `architecture.json > deferrals.platform_implementer` were implemented. No TODO markers left.
