"""
CalendarConnector HTTP router.

Defines seven endpoints (Sprint01 x4, Sprint02 x1 updated, Sprint03 x2 new):
  1. GET  /calendar/google/connect/start        — initiate Google consent flow
  2. GET  /calendar/google/connect/callback     — receive auth code, exchange tokens
  3. GET  /calendar/events                      — return Dataset of calendar events
  4. GET  /calendar/status                      — return Dataset of connection health
  5. POST /calendar/events                      — idempotent create (Sprint02, retrofitted Sprint03)
  6. PATCH  /calendar/events/{atlas_event_id}   — update existing event (Sprint03)
  7. DELETE /calendar/events/{atlas_event_id}   — idempotent delete (Sprint03)

The router is mounted at prefix /api in main.py, so effective paths are:
  /api/calendar/google/connect/start
  /api/calendar/google/connect/callback
  /api/calendar/events          (GET, POST, PATCH /{id}, DELETE /{id})
  /api/calendar/status

Invariants enforced here:
- Token values (access_token, refresh_token) are NEVER included in any response.
- All errors use api_error().
- GET events and status always return Dataset.
- POST events returns CalendarEventOperationResult as JSON (201 on 'created', 200 on 'existing').
- PATCH events returns CalendarEventOperationResult as JSON 200.
- DELETE events returns CalendarDeleteResult as JSON 200.
- CSRF nonce is deleted (consumed) on first use in callback.
- POST/PATCH/DELETE always write to CALENDAR_TARGET_CALENDAR_ID — never to a caller-supplied ID.
- Decision log is written best-effort for every write attempt.
- Index write failure after Google create is a hard error (INDEX_WRITE_FAILURE, not silent).
- _get_valid_access_token() is used by all three write handlers; callers MUST isinstance-check
  the return — JSONResponse means early return, str means a valid access token.
"""
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse

from platform_contracts.contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling.api_response import api_error

from app.database import get_db
from app.models import (
    CalendarConnectionStatusRow,
    CalendarCreateEventRequest,
    CalendarDeleteResult,
    CalendarEventOperationResult,
    CalendarEventRow,
    CalendarUpdateEventRequest,
)
from app.services import calendar_api, google_oauth, token_store
from app.services.calendar_api import GoogleEventNotFoundError

log = logging.getLogger("calendar_connector")

router = APIRouter()

# Nonce TTL: 10 minutes is generous for a browser round-trip to Google
_STATE_TTL_MINUTES = 10


def _callback_uri() -> str:
    """Build the OAuth callback URI from environment.

    Uses CALENDAR_CALLBACK_URI if set, otherwise builds from CALENDAR_CONNECTOR_PORT.
    The URI must match what is registered in Google Cloud Console.
    """
    if uri := os.environ.get("CALENDAR_CALLBACK_URI"):
        return uri
    port = os.environ.get("CALENDAR_CONNECTOR_PORT", "8021")
    return f"http://localhost:{port}/api/calendar/google/connect/callback"


def _validate_target_calendar_id() -> None:
    """Validate that CALENDAR_TARGET_CALENDAR_ID is set in the environment.

    Called at startup (from main.py on_startup). Raises RuntimeError if absent.
    Fail-fast: consistent with _client_id() / _client_secret() in google_oauth.py.
    """
    val = os.environ.get("CALENDAR_TARGET_CALENDAR_ID", "")
    if not val:
        raise RuntimeError(
            "CALENDAR_TARGET_CALENDAR_ID environment variable is not set. "
            "Add it to 01_System/config.env before starting CalendarConnector."
        )


def _target_calendar_id() -> str:
    """Return the operator-configured target calendar ID.

    The POST /api/calendar/events endpoint always writes to this calendar.
    The caller cannot override this value.
    """
    val = os.environ.get("CALENDAR_TARGET_CALENDAR_ID", "")
    if not val:
        raise RuntimeError("CALENDAR_TARGET_CALENDAR_ID not configured")
    return val


# Scope string that indicates write-capable calendar access
_WRITE_SCOPE = "https://www.googleapis.com/auth/calendar"

# Write scope does not contain 'calendar.readonly' — but 'calendar' is a substring
# of 'calendar.readonly'. Use a check that distinguishes the two:
# - calendar.readonly: only read
# - calendar: read + write (what we need)
# The Google-returned scope for the full calendar permission is exactly the string above.
# We check for the write scope by verifying the full scope string is present, not just
# that 'calendar' appears as a substring.
def _has_write_scope(granted_scopes: str) -> bool:
    """Return True if the granted_scopes string includes the write-capable calendar scope."""
    # granted_scopes is space-separated; check each token
    scopes = granted_scopes.split()
    return _WRITE_SCOPE in scopes


# ---------------------------------------------------------------------------
# Shared helper: _get_valid_access_token
# ---------------------------------------------------------------------------

def _get_valid_access_token(
    conn: "psycopg2.extensions.connection",
    connection: dict,
    token: dict,
) -> "str | JSONResponse":
    """Validate and (if needed) refresh the stored access token.

    Returns a valid access_token string on success.
    Returns a JSONResponse (api_error) on CALENDAR_TOKEN_EXPIRED or CALENDAR_ACCESS_REVOKED.

    CALL-SITE OBLIGATION: every caller must branch on isinstance(result, JSONResponse).
    If the return value is a JSONResponse it must be returned immediately to FastAPI.
    Never pass a JSONResponse return value to Google API code.

    This helper must be called inside a `with get_db() as conn:` block so that token
    upserts from a refresh are committed before the network call to Google.
    """
    access_token = token["access_token"]
    token_expiry: datetime = token["token_expiry"]

    # Normalize to UTC-aware if needed
    if token_expiry.tzinfo is None:
        token_expiry = token_expiry.replace(tzinfo=timezone.utc)

    # Token still valid — return immediately
    if datetime.now(timezone.utc) < token_expiry:
        return access_token

    # Token is expired — attempt refresh
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        token_store.update_connection_status(
            conn,
            status="expired",
            last_error="Token expired and no refresh_token stored",
        )
        return api_error(
            code="CALENDAR_TOKEN_EXPIRED",
            message="Calendar access token is expired and cannot be refreshed",
            status=503,
        )

    try:
        refreshed = google_oauth.refresh_access_token(refresh_token)
    except ValueError as exc:
        err_msg = str(exc)
        if "401" in err_msg or "403" in err_msg or "invalid_grant" in err_msg.lower():
            token_store.update_connection_status(
                conn,
                status="revoked",
                last_error=err_msg,
            )
            return api_error(
                code="CALENDAR_ACCESS_REVOKED",
                message="Google has revoked calendar access. Reconnect at /api/calendar/google/connect/start",
                status=503,
            )
        token_store.update_connection_status(
            conn,
            status="expired",
            last_error=err_msg,
        )
        return api_error(
            code="CALENDAR_TOKEN_EXPIRED",
            message="Calendar access token refresh failed",
            detail=err_msg,
            status=503,
        )

    new_expires_in = refreshed.get("expires_in", 3600)
    new_expiry = (
        datetime.now(timezone.utc) + timedelta(seconds=int(new_expires_in))
    ).isoformat()
    token_store.upsert_token(
        conn,
        connection_id=connection["id"],
        access_token=refreshed["access_token"],
        refresh_token=refresh_token,  # Google does not re-issue refresh_token
        token_expiry=new_expiry,
        token_type=refreshed.get("token_type"),
        scope=refreshed.get("scope"),
    )
    log.info("Access token refreshed successfully")
    return refreshed["access_token"]


# ---------------------------------------------------------------------------
# Step 1: connect_start
# ---------------------------------------------------------------------------

@router.get("/calendar/google/connect/start")
def connect_start() -> RedirectResponse:
    """Generate CSRF nonce, persist it, return RedirectResponse to Google consent URL.

    Scope requested: https://www.googleapis.com/auth/calendar.readonly
    This is a separate flow from Atlas Google login — it does NOT affect login state.
    """
    nonce = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=_STATE_TTL_MINUTES)
    ).isoformat()

    with get_db() as conn:
        token_store.create_oauth_state(conn, nonce, expires_at)

    auth_url = google_oauth.build_authorization_url(
        state=nonce,
        redirect_uri=_callback_uri(),
    )
    log.info("Redirecting to Google consent screen for calendar access")
    return RedirectResponse(url=auth_url, status_code=302)


# ---------------------------------------------------------------------------
# Step 2: connect_callback
# ---------------------------------------------------------------------------

@router.get("/calendar/google/connect/callback")
def connect_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
) -> JSONResponse:
    """Validate CSRF nonce, exchange auth code for tokens, upsert connection/token records.

    Returns 200 JSON on success, api_error on any failure.
    Nonce is deleted (one-time use) before token exchange begins.
    """
    # Google may return error=access_denied or similar
    if error:
        log.warning("Google returned error in callback: %s", error)
        return api_error(
            code="OAUTH_DENIED",
            message=f"Google returned an error: {error}",
            status=400,
        )

    if not code or not state:
        return api_error(
            code="OAUTH_STATE_MISMATCH",
            message="Missing code or state parameter in callback",
            status=400,
        )

    # Validate and consume CSRF nonce (one-time use, expires_at enforced in DB)
    with get_db() as conn:
        valid = token_store.consume_oauth_state(conn, state)

    if not valid:
        log.warning("CSRF state mismatch or expired nonce in OAuth callback")
        return api_error(
            code="OAUTH_STATE_MISMATCH",
            message="OAuth state parameter is invalid or expired",
            status=400,
        )

    # Exchange auth code for tokens
    redirect_uri = _callback_uri()
    try:
        token_data = google_oauth.exchange_code_for_tokens(code, redirect_uri)
    except ValueError as exc:
        log.error("Token exchange failed: %s", exc)
        return api_error(
            code="GOOGLE_API_ERROR",
            message="Failed to exchange authorization code for tokens",
            detail=str(exc),
            status=502,
        )

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    token_type = token_data.get("token_type", "Bearer")
    scope = token_data.get("scope", "")

    token_expiry = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    ).isoformat()

    # Fetch account email via userinfo endpoint (no JWT library required)
    account_email = google_oauth.get_account_email(access_token)

    # Persist connection and token state
    with get_db() as conn:
        connection_id = token_store.upsert_connection(
            conn,
            provider="google",
            account_email=account_email,
            status="connected",
            granted_scopes=scope,
        )
        token_store.upsert_token(
            conn,
            connection_id=connection_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            token_type=token_type,
            scope=scope,
        )

    log.info(
        "Calendar connection established for account=%s connection_id=%s",
        account_email,
        connection_id,
    )
    return JSONResponse(
        status_code=200,
        content={
            "status": "connected",
            "account_email": account_email,
            "message": "Google Calendar connection established successfully.",
        },
    )


# ---------------------------------------------------------------------------
# Step 4: get_events
# ---------------------------------------------------------------------------

@router.get("/calendar/events", response_model=None)
def get_events(
    from_: str = Query(alias="from"),
    to: str = Query(),
) -> Dataset | JSONResponse:
    """Check connection, refresh token if needed, fetch Google Calendar events.

    Returns Dataset with object_type=calendar_event.
    Returns api_error if no connection exists, token is expired/revoked, or Google fails.

    Sprint03 refactor: uses _get_valid_access_token() helper for token refresh logic.
    """
    with get_db() as conn:
        connection = token_store.get_connection(conn)
        if not connection:
            return api_error(
                code="NO_CALENDAR_CONNECTION",
                message="No calendar connection found. Connect at /api/calendar/google/connect/start",
                status=404,
            )

        token = token_store.get_token(conn)
        if not token:
            return api_error(
                code="NO_CALENDAR_CONNECTION",
                message="No token found for calendar connection",
                status=404,
            )

        access_token = _get_valid_access_token(conn, connection, token)
        if isinstance(access_token, JSONResponse):
            return access_token

    # Fetch events from Google Calendar (outside DB context — network call)
    try:
        event_rows = calendar_api.fetch_events(access_token, from_dt=from_, to_dt=to)
    except ValueError as exc:
        log.error("Google Calendar API error: %s", exc)
        with get_db() as conn:
            token_store.update_connection_status(
                conn,
                status="error",
                last_error=str(exc),
            )
        return api_error(
            code="GOOGLE_API_ERROR",
            message="Google Calendar API request failed",
            detail=str(exc),
            status=502,
        )

    # Record successful fetch
    with get_db() as conn:
        token_store.record_success(conn)

    rows = [row.model_dump() for row in event_rows]

    return Dataset(
        meta=DatasetMeta(
            object_type="calendar_event",
            label="Calendar Events",
            total=len(rows),
            page=1,
            page_size=len(rows),
            row_actions=[],
        ),
        **{"schema": [
            ColumnSchema(key="id",                   label="Event ID",        type="string",  sortable=False, detail_visible=False),
            ColumnSchema(key="title",                label="Title",           type="string",  sortable=True),
            ColumnSchema(key="start_at",             label="Start",           type="date",    sortable=True),
            ColumnSchema(key="end_at",               label="End",             type="date",    sortable=True),
            ColumnSchema(key="all_day",              label="All Day",         type="boolean", sortable=False),
            ColumnSchema(key="status",               label="Status",          type="string",  sortable=False),
            ColumnSchema(key="location",             label="Location",        type="string",  sortable=False),
            ColumnSchema(key="description",          label="Description",     type="string",  sortable=False, detail_visible=True),
            ColumnSchema(key="source_calendar_id",   label="Calendar ID",     type="string",  sortable=False, detail_visible=False),
            ColumnSchema(key="source_calendar_label",label="Calendar",        type="string",  sortable=False),
        ]},
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Step 5: get_status
# ---------------------------------------------------------------------------

@router.get("/calendar/status")
def get_status() -> Dataset:
    """Read calendar_connection record and return Dataset with object_type=calendar_connection.

    Always returns a Dataset. Returns a single row with status='not_connected' if no
    connection record exists. Never returns api_error.
    No token values are included in the response.
    """
    with get_db() as conn:
        connection = token_store.get_connection(conn)

    if not connection:
        # Return a Dataset with a single 'not connected' status row
        not_connected_row = CalendarConnectionStatusRow(
            id="system",
            provider="google",
            account_email=None,
            status="not_connected",
            granted_scopes="",
            last_success_at=None,
            last_error=None,
            created_at="",
            updated_at="",
        )
        rows = [not_connected_row.model_dump()]
    else:
        status_row = CalendarConnectionStatusRow(
            id="system",
            provider=connection["provider"],
            account_email=connection.get("account_email"),
            status=connection["status"],
            granted_scopes=connection.get("granted_scopes", ""),
            last_success_at=(
                connection["last_success_at"].isoformat()
                if connection.get("last_success_at")
                else None
            ),
            last_error=connection.get("last_error"),
            created_at=connection["created_at"].isoformat() if connection.get("created_at") else "",
            updated_at=connection["updated_at"].isoformat() if connection.get("updated_at") else "",
        )
        rows = [status_row.model_dump()]

    return Dataset(
        meta=DatasetMeta(
            object_type="calendar_connection",
            label="Calendar Connection",
            total=1,
            page=1,
            page_size=1,
            row_actions=["disconnect"] if connection else [],
        ),
        **{"schema": [
            ColumnSchema(key="id",              label="ID",             type="string",  sortable=False, detail_visible=False),
            ColumnSchema(key="provider",        label="Provider",       type="string",  sortable=False),
            ColumnSchema(key="account_email",   label="Account",        type="string",  sortable=False),
            ColumnSchema(key="status",          label="Status",         type="string",  sortable=False),
            ColumnSchema(key="granted_scopes",  label="Granted Scopes", type="string",  sortable=False),
            ColumnSchema(key="last_success_at", label="Last Success",   type="date",    sortable=False),
            ColumnSchema(key="last_error",      label="Last Error",     type="string",  sortable=False),
            ColumnSchema(key="created_at",      label="Connected At",   type="date",    sortable=False),
            ColumnSchema(key="updated_at",      label="Updated At",     type="date",    sortable=False),
        ]},
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Step 6: create_event (Sprint02, retrofitted Sprint03)
# ---------------------------------------------------------------------------

def _check_connection_and_scope(
    conn: "psycopg2.extensions.connection",
) -> "tuple[dict, dict] | JSONResponse":
    """Fetch connection + token rows and validate write scope.

    Returns (connection, token) on success.
    Returns a JSONResponse on any failure (NO_CALENDAR_CONNECTION or INSUFFICIENT_SCOPE).

    CALL-SITE OBLIGATION: check isinstance(result, JSONResponse) and return immediately.
    """
    connection = token_store.get_connection(conn)
    if not connection:
        return api_error(
            code="NO_CALENDAR_CONNECTION",
            message="No calendar connection found. Connect at /api/calendar/google/connect/start",
            status=404,
        )

    token = token_store.get_token(conn)
    if not token:
        return api_error(
            code="NO_CALENDAR_CONNECTION",
            message="No token found for calendar connection",
            status=404,
        )

    granted_scopes = connection.get("granted_scopes", "") or ""
    if not _has_write_scope(granted_scopes):
        log.warning(
            "Write attempt rejected: connection has insufficient scope. granted_scopes=%r",
            granted_scopes,
        )
        return api_error(
            code="INSUFFICIENT_SCOPE",
            message=(
                "The calendar connection does not have write access. "
                "Re-run GET /api/calendar/google/connect/start to grant write-capable scope."
            ),
            detail={"granted_scopes": granted_scopes, "required_scope": _WRITE_SCOPE},
            status=403,
        )

    return connection, token


@router.post("/calendar/events", response_model=None, status_code=201)
def create_event(request: CalendarCreateEventRequest) -> JSONResponse:
    """Create a Google Calendar event idempotently by atlas_event_id.

    Sprint03 retrofit: idempotent create behavior.
    - If an active index entry exists for atlas_event_id, returns the existing mapping
      with status='existing' (HTTP 200). No Google API call is made.
    - If no active entry exists, creates the event in Google Calendar, writes the index
      entry, and returns status='created' (HTTP 201).
    - INDEX_WRITE_FAILURE is a hard error — if the Google event is created but the index
      write fails, the request returns 500 (not silent success).

    Invariants:
    - Target calendar is always CALENDAR_TARGET_CALENDAR_ID (env var). Caller cannot override.
    - Requires write-capable OAuth scope.
    - Decision log entry is written best-effort for every attempt.
    - atlas_event_id is stored in Google extendedProperties.private.atlas_event_id.
    """
    requested_at = datetime.now(timezone.utc).isoformat()
    target_calendar_id = _target_calendar_id()

    with get_db() as conn:
        check = _check_connection_and_scope(conn)
        if isinstance(check, JSONResponse):
            return check
        connection, token = check

        access_token = _get_valid_access_token(conn, connection, token)
        if isinstance(access_token, JSONResponse):
            return access_token

        # Idempotency check: look up atlas_event_id in event index
        index_row = token_store.get_event_index_by_atlas_id(conn, request.atlas_event_id)

    if index_row and index_row["status"] == "active":
        # Active mapping exists — return existing event reference, no Google call
        log.info(
            "Idempotent create: returning existing mapping for atlas_event_id=%s google_event_id=%s",
            request.atlas_event_id,
            index_row["google_event_id"],
        )
        result = CalendarEventOperationResult(
            status="existing",
            atlas_event_id=request.atlas_event_id,
            google_event_id=index_row["google_event_id"],
            title=request.title,
            start_at=request.start_at,
            end_at=request.end_at,
            all_day=request.all_day,
            source_calendar_id=index_row["calendar_id"],
            source_calendar_label=None,
        )
        # Best-effort decision log
        try:
            with get_db() as conn:
                token_store.write_decision_log(
                    conn,
                    operation="calendar_event_create",
                    requested_at=requested_at,
                    target_calendar_id=target_calendar_id,
                    outcome="success",
                    google_event_id=index_row["google_event_id"],
                    error_summary=None,
                    atlas_event_id=request.atlas_event_id,
                )
        except Exception as log_exc:
            log.error("Failed to write decision log (existing case): %s", log_exc)
        return JSONResponse(status_code=200, content=result.model_dump())

    # No active mapping — proceed to create in Google Calendar
    try:
        result = calendar_api.create_event(access_token, target_calendar_id, request)
    except ValueError as exc:
        err_msg = str(exc)
        log.error("Google Calendar API error on create_event: %s", err_msg)
        try:
            with get_db() as conn:
                token_store.write_decision_log(
                    conn,
                    operation="calendar_event_create",
                    requested_at=requested_at,
                    target_calendar_id=target_calendar_id,
                    outcome="failure",
                    google_event_id=None,
                    error_summary=err_msg[:1000],
                    atlas_event_id=request.atlas_event_id,
                )
        except Exception as log_exc:
            log.error("Failed to write decision log (Google failure case): %s", log_exc)
        return api_error(
            code="GOOGLE_API_ERROR",
            message="Google Calendar API request failed during event creation",
            detail=err_msg,
            status=502,
        )

    # Google event created — write index entry (hard error if this fails)
    try:
        with get_db() as conn:
            token_store.upsert_event_index(
                conn,
                atlas_event_id=request.atlas_event_id,
                google_event_id=result.google_event_id,
                calendar_id=target_calendar_id,
            )
    except Exception as index_exc:
        err_msg = str(index_exc)
        log.error(
            "INDEX_WRITE_FAILURE: Google event created (google_event_id=%s) but index write failed: %s",
            result.google_event_id,
            err_msg,
        )
        # Best-effort decision log for the index failure
        try:
            with get_db() as conn:
                token_store.write_decision_log(
                    conn,
                    operation="calendar_event_create",
                    requested_at=requested_at,
                    target_calendar_id=target_calendar_id,
                    outcome="failure",
                    google_event_id=result.google_event_id,
                    error_summary=f"INDEX_WRITE_FAILURE: {err_msg[:900]}",
                    atlas_event_id=request.atlas_event_id,
                )
        except Exception as log_exc:
            log.error("Failed to write decision log (index failure case): %s", log_exc)
        return api_error(
            code="INDEX_WRITE_FAILURE",
            message="Google event was created but the internal event index write failed",
            detail={
                "google_event_id": result.google_event_id,
                "atlas_event_id": request.atlas_event_id,
                "error": err_msg,
            },
            status=500,
        )

    # Best-effort decision log for success
    try:
        with get_db() as conn:
            token_store.write_decision_log(
                conn,
                operation="calendar_event_create",
                requested_at=requested_at,
                target_calendar_id=target_calendar_id,
                outcome="success",
                google_event_id=result.google_event_id,
                error_summary=None,
                atlas_event_id=request.atlas_event_id,
            )
    except Exception as log_exc:
        log.error("Failed to write decision log (success case): %s", log_exc)

    log.info(
        "Calendar event created: google_event_id=%s atlas_event_id=%s calendar=%s",
        result.google_event_id,
        request.atlas_event_id,
        target_calendar_id,
    )
    return JSONResponse(status_code=201, content=result.model_dump())


# ---------------------------------------------------------------------------
# Step 7: update_event (Sprint03)
# ---------------------------------------------------------------------------

@router.patch("/calendar/events/{atlas_event_id}", response_model=None)
def update_event(
    atlas_event_id: str,
    request: CalendarUpdateEventRequest,
) -> JSONResponse:
    """Update an existing Atlas-linked Google Calendar event.

    Resolves the Google event via the internal event index.
    Returns EVENT_NOT_FOUND (404) if no active index entry exists.
    Returns GOOGLE_EVENT_NOT_FOUND (404) if the index entry is active but Google returns 404;
      sets index status to 'error' in this case.
    Returns CalendarEventOperationResult with status='updated' (HTTP 200) on success.

    At least one updatable field must be present in the request body (NO_UPDATE_FIELDS 400).
    Decision log entry is written best-effort for every attempt.
    """
    requested_at = datetime.now(timezone.utc).isoformat()
    target_calendar_id = _target_calendar_id()

    # Validate that at least one field was provided
    updatable = {
        k: v for k, v in request.model_dump().items() if v is not None
    }
    if not updatable:
        return api_error(
            code="NO_UPDATE_FIELDS",
            message="PATCH body must contain at least one updatable field",
            detail={"updatable_fields": ["title", "start_at", "end_at", "description", "location", "all_day"]},
            status=400,
        )

    with get_db() as conn:
        check = _check_connection_and_scope(conn)
        if isinstance(check, JSONResponse):
            return check
        connection, token = check

        access_token = _get_valid_access_token(conn, connection, token)
        if isinstance(access_token, JSONResponse):
            return access_token

        index_row = token_store.get_event_index_by_atlas_id(conn, atlas_event_id)

    # Only active index entries are resolvable for update
    if not index_row or index_row["status"] != "active":
        return api_error(
            code="EVENT_NOT_FOUND",
            message=f"No active calendar event mapping found for atlas_event_id={atlas_event_id!r}",
            detail={"atlas_event_id": atlas_event_id},
            status=404,
        )

    google_event_id = index_row["google_event_id"]

    try:
        result = calendar_api.update_event(
            access_token,
            target_calendar_id,
            google_event_id,
            request,
            atlas_event_id,
        )
    except GoogleEventNotFoundError as exc:
        err_msg = str(exc)
        log.warning(
            "Google event missing during update: atlas_event_id=%s google_event_id=%s",
            atlas_event_id,
            google_event_id,
        )
        # Mark index entry as error — requires operator attention
        try:
            with get_db() as conn:
                token_store.mark_event_index_error(
                    conn,
                    atlas_event_id=atlas_event_id,
                    error_summary=err_msg[:1000],
                )
        except Exception as idx_exc:
            log.error("Failed to mark index error: %s", idx_exc)
        # Best-effort decision log
        try:
            with get_db() as conn:
                token_store.write_decision_log(
                    conn,
                    operation="calendar_event_update",
                    requested_at=requested_at,
                    target_calendar_id=target_calendar_id,
                    outcome="failure",
                    google_event_id=google_event_id,
                    error_summary=err_msg[:1000],
                    atlas_event_id=atlas_event_id,
                )
        except Exception as log_exc:
            log.error("Failed to write decision log (GOOGLE_EVENT_NOT_FOUND): %s", log_exc)
        return api_error(
            code="GOOGLE_EVENT_NOT_FOUND",
            message="The mapped Google event no longer exists. Index status set to 'error'.",
            detail={"atlas_event_id": atlas_event_id, "google_event_id": google_event_id},
            status=404,
        )
    except ValueError as exc:
        err_msg = str(exc)
        log.error("Google Calendar API error on update_event: %s", err_msg)
        try:
            with get_db() as conn:
                token_store.write_decision_log(
                    conn,
                    operation="calendar_event_update",
                    requested_at=requested_at,
                    target_calendar_id=target_calendar_id,
                    outcome="failure",
                    google_event_id=google_event_id,
                    error_summary=err_msg[:1000],
                    atlas_event_id=atlas_event_id,
                )
        except Exception as log_exc:
            log.error("Failed to write decision log (update Google failure): %s", log_exc)
        return api_error(
            code="GOOGLE_API_ERROR",
            message="Google Calendar API request failed during event update",
            detail=err_msg,
            status=502,
        )

    # Best-effort decision log for success
    try:
        with get_db() as conn:
            token_store.write_decision_log(
                conn,
                operation="calendar_event_update",
                requested_at=requested_at,
                target_calendar_id=target_calendar_id,
                outcome="success",
                google_event_id=result.google_event_id,
                error_summary=None,
                atlas_event_id=atlas_event_id,
            )
    except Exception as log_exc:
        log.error("Failed to write decision log (update success): %s", log_exc)

    log.info(
        "Calendar event updated: google_event_id=%s atlas_event_id=%s",
        result.google_event_id,
        atlas_event_id,
    )
    return JSONResponse(status_code=200, content=result.model_dump())


# ---------------------------------------------------------------------------
# Step 8: delete_event (Sprint03)
# ---------------------------------------------------------------------------

@router.delete("/calendar/events/{atlas_event_id}", response_model=None)
def delete_event(atlas_event_id: str) -> JSONResponse:
    """Idempotently delete an Atlas-linked Google Calendar event.

    Resolves the event through the internal event index.
    - No index row at all: returns success with google_event_id=None (never existed).
    - Index row status='deleted': returns success without calling Google (already deleted).
    - Index row status='active': calls Google Calendar API delete.
      - Google 404 (already missing): marks index as 'deleted', returns success.
      - Google 204 (successful delete): marks index as 'deleted', returns success.

    Decision log entry is written best-effort for every attempt.
    """
    requested_at = datetime.now(timezone.utc).isoformat()
    target_calendar_id = _target_calendar_id()

    with get_db() as conn:
        check = _check_connection_and_scope(conn)
        if isinstance(check, JSONResponse):
            return check
        connection, token = check

        access_token = _get_valid_access_token(conn, connection, token)
        if isinstance(access_token, JSONResponse):
            return access_token

        index_row = token_store.get_event_index_by_atlas_id(conn, atlas_event_id)

    # Idempotent: no index row at all — event was never created through Atlas
    if index_row is None:
        log.info("Idempotent delete: no index row for atlas_event_id=%s", atlas_event_id)
        try:
            with get_db() as conn:
                token_store.write_decision_log(
                    conn,
                    operation="calendar_event_delete",
                    requested_at=requested_at,
                    target_calendar_id=target_calendar_id,
                    outcome="success",
                    google_event_id=None,
                    error_summary=None,
                    atlas_event_id=atlas_event_id,
                )
        except Exception as log_exc:
            log.error("Failed to write decision log (no index row): %s", log_exc)
        result = CalendarDeleteResult(
            status="deleted",
            atlas_event_id=atlas_event_id,
            google_event_id=None,
        )
        return JSONResponse(status_code=200, content=result.model_dump())

    google_event_id = index_row["google_event_id"]

    # Idempotent: index row already marked deleted
    if index_row["status"] == "deleted":
        log.info(
            "Idempotent delete: index row already deleted for atlas_event_id=%s",
            atlas_event_id,
        )
        try:
            with get_db() as conn:
                token_store.write_decision_log(
                    conn,
                    operation="calendar_event_delete",
                    requested_at=requested_at,
                    target_calendar_id=target_calendar_id,
                    outcome="success",
                    google_event_id=google_event_id,
                    error_summary=None,
                    atlas_event_id=atlas_event_id,
                )
        except Exception as log_exc:
            log.error("Failed to write decision log (already deleted): %s", log_exc)
        result = CalendarDeleteResult(
            status="deleted",
            atlas_event_id=atlas_event_id,
            google_event_id=google_event_id,
        )
        return JSONResponse(status_code=200, content=result.model_dump())

    # Active (or error) index row — attempt remote deletion
    try:
        found = calendar_api.delete_event(access_token, target_calendar_id, google_event_id)
    except ValueError as exc:
        err_msg = str(exc)
        log.error("Google Calendar API error on delete_event: %s", err_msg)
        try:
            with get_db() as conn:
                token_store.write_decision_log(
                    conn,
                    operation="calendar_event_delete",
                    requested_at=requested_at,
                    target_calendar_id=target_calendar_id,
                    outcome="failure",
                    google_event_id=google_event_id,
                    error_summary=err_msg[:1000],
                    atlas_event_id=atlas_event_id,
                )
        except Exception as log_exc:
            log.error("Failed to write decision log (delete Google failure): %s", log_exc)
        return api_error(
            code="GOOGLE_API_ERROR",
            message="Google Calendar API request failed during event deletion",
            detail=err_msg,
            status=502,
        )

    # Mark index as deleted regardless of whether Google returned 204 or 404
    note = None if found else "remote event was already absent (Google 404)"
    try:
        with get_db() as conn:
            token_store.mark_event_index_deleted(
                conn,
                atlas_event_id=atlas_event_id,
                note=note,
            )
    except Exception as idx_exc:
        log.error("Failed to mark index deleted for atlas_event_id=%s: %s", atlas_event_id, idx_exc)
        # Do not surface this as an error to the caller — the remote delete succeeded.

    # Best-effort decision log
    try:
        with get_db() as conn:
            token_store.write_decision_log(
                conn,
                operation="calendar_event_delete",
                requested_at=requested_at,
                target_calendar_id=target_calendar_id,
                outcome="success",
                google_event_id=google_event_id,
                error_summary=note,
                atlas_event_id=atlas_event_id,
            )
    except Exception as log_exc:
        log.error("Failed to write decision log (delete success): %s", log_exc)

    log.info(
        "Calendar event deleted: google_event_id=%s atlas_event_id=%s found_remotely=%s",
        google_event_id,
        atlas_event_id,
        found,
    )
    result = CalendarDeleteResult(
        status="deleted",
        atlas_event_id=atlas_event_id,
        google_event_id=google_event_id,
    )
    return JSONResponse(status_code=200, content=result.model_dump())
