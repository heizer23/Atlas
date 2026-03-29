"""
CalendarConnector HTTP router.

Defines all four exposed endpoints per architecture.json internal_flow:
  1. GET /calendar/google/connect/start   — initiate Google consent flow
  2. GET /calendar/google/connect/callback — receive auth code, exchange tokens
  3. GET /calendar/events                  — return Dataset of calendar events
  4. GET /calendar/status                  — return Dataset of connection health

The router is mounted at prefix /api in main.py, so effective paths are:
  /api/calendar/google/connect/start
  /api/calendar/google/connect/callback
  /api/calendar/events
  /api/calendar/status

Invariants enforced here:
- Token values (access_token, refresh_token) are NEVER included in any response.
- All errors use api_error().
- Events and status always return Dataset.
- CSRF nonce is deleted (consumed) on first use in callback.
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
from app.models import CalendarConnectionStatusRow, CalendarEventRow
from app.services import calendar_api, google_oauth, token_store

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

        access_token = token["access_token"]
        token_expiry: datetime = token["token_expiry"]

        # Normalize to UTC-aware if needed
        if token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=timezone.utc)

        # Lazy token refresh: refresh if expired
        if datetime.now(timezone.utc) >= token_expiry:
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
                # Determine if Google revoked access (4xx on refresh)
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

            # Persist refreshed token
            new_expires_in = refreshed.get("expires_in", 3600)
            new_expiry = (
                datetime.now(timezone.utc) + timedelta(seconds=int(new_expires_in))
            ).isoformat()
            token_store.upsert_token(
                conn,
                connection_id=connection["id"],
                access_token=refreshed["access_token"],
                refresh_token=refresh_token,  # refresh_token not re-issued by Google
                token_expiry=new_expiry,
                token_type=refreshed.get("token_type"),
                scope=refreshed.get("scope"),
            )
            access_token = refreshed["access_token"]
            log.info("Access token refreshed successfully")

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
