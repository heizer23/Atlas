"""
Pydantic models for CalendarConnector request/response shapes.

Sprint01 models:
  CalendarEventRow          — Dataset row shape for GET /api/calendar/events
  CalendarConnectionStatusRow — Dataset row shape for GET /api/calendar/status

Sprint02 additions:
  CalendarCreateEventRequest  — Request body for POST /api/calendar/events
  CalendarCreateEventResult   — Kept as alias; renamed to CalendarEventOperationResult in Sprint03

Sprint03 additions / retrofits:
  CalendarCreateEventRequest  — atlas_event_id field added (required)
  CalendarEventOperationResult — renamed from CalendarCreateEventResult; atlas_event_id added;
                                  status widened to Literal['created', 'existing', 'updated']
  CalendarUpdateEventRequest  — Request body for PATCH /api/calendar/events/{atlas_event_id}
  CalendarDeleteResult        — Response for DELETE /api/calendar/events/{atlas_event_id}

Token fields (access_token, refresh_token) are never included here.
"""
from typing import Literal, Optional

from pydantic import BaseModel


class CalendarEventRow(BaseModel):
    """Row shape for object_type 'calendar_event' in Dataset rows."""

    id: str                          # Google event id — used as Dataset row id
    title: str                       # event summary
    description: Optional[str]       # event description (may be None)
    start_at: str                    # ISO8601 string
    end_at: str                      # ISO8601 string
    all_day: str                     # "true" or "false" — string to satisfy ColumnType rules
    location: Optional[str]          # event location (may be None)
    status: str                      # Google event status: confirmed | tentative | cancelled
    source_calendar_id: str          # calendar id the event was fetched from
    source_calendar_label: Optional[str]  # human-readable calendar label if available


class CalendarConnectionStatusRow(BaseModel):
    """Row shape for object_type 'calendar_connection' in Dataset rows.

    id is always the fixed string 'system' — this is a system-scoped singleton.
    Token fields are never included.
    """

    id: str = "system"              # fixed value — system-scoped singleton row
    provider: str
    account_email: Optional[str]
    status: str                     # connected | expired | revoked | error | not_connected
    granted_scopes: str
    last_success_at: Optional[str]  # ISO8601 string or None
    last_error: Optional[str]
    created_at: str                 # ISO8601 string
    updated_at: str                 # ISO8601 string


# ---------------------------------------------------------------------------
# Sprint02 additions — write capability (retrofitted in Sprint03)
# ---------------------------------------------------------------------------

class CalendarCreateEventRequest(BaseModel):
    """Request body for POST /api/calendar/events.

    atlas_event_id, title, start_at, end_at are required.
    description, location, all_day are optional.
    calendar_id is NOT accepted — target calendar is always operator-configured.

    Sprint03: atlas_event_id added (required). Used as stable cross-system identity key.
    """

    atlas_event_id: str              # stable Atlas-side identifier; used for idempotency
    title: str
    start_at: str                    # ISO8601 datetime string (or YYYY-MM-DD if all_day=True)
    end_at: str                      # ISO8601 datetime string (or YYYY-MM-DD if all_day=True)
    description: Optional[str] = None
    location: Optional[str] = None
    all_day: bool = False            # if True, use date-only format in Google API call


class CalendarEventOperationResult(BaseModel):
    """Success response for POST /api/calendar/events (create or idempotent return),
    and PATCH /api/calendar/events/{atlas_event_id} (update).

    Not a Dataset row — this is a direct JSON success payload.
    POST returns 201 on status='created', 200 on status='existing'.
    PATCH returns 200 on status='updated'.
    """

    status: Literal["created", "existing", "updated"]
    atlas_event_id: str              # stable Atlas-side identifier
    google_event_id: str             # Google Calendar event id
    title: str
    start_at: str                    # ISO8601 string as returned by Google
    end_at: str                      # ISO8601 string as returned by Google
    all_day: bool                    # native bool (not string — this is not a Dataset row)
    source_calendar_id: str          # the target calendar ID used
    source_calendar_label: Optional[str]  # calendar summary from Google response, if available


# Sprint02 name kept as alias so existing imports do not need a global search-replace
# during the transition. Implementer note: new code should use CalendarEventOperationResult.
CalendarCreateEventResult = CalendarEventOperationResult


# ---------------------------------------------------------------------------
# Sprint03 additions
# ---------------------------------------------------------------------------

class CalendarUpdateEventRequest(BaseModel):
    """Request body for PATCH /api/calendar/events/{atlas_event_id}.

    All fields are optional — the handler validates that at least one is present.
    calendar_id is NOT accepted — target calendar is always operator-configured.
    """

    title: Optional[str] = None
    start_at: Optional[str] = None   # ISO8601 datetime string (or YYYY-MM-DD if all_day=True)
    end_at: Optional[str] = None     # ISO8601 datetime string (or YYYY-MM-DD if all_day=True)
    description: Optional[str] = None
    location: Optional[str] = None
    all_day: Optional[bool] = None


class CalendarDeleteResult(BaseModel):
    """Success response for DELETE /api/calendar/events/{atlas_event_id}.

    Returned as JSONResponse with status_code=200.
    google_event_id is None when the atlas_event_id had no index entry at all.
    """

    status: Literal["deleted"] = "deleted"
    atlas_event_id: str
    google_event_id: Optional[str]   # None if no index row existed
