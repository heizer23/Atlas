"""
Pydantic models for CalendarConnector request/response shapes.

Sprint01 models:
  CalendarEventRow          — Dataset row shape for GET /api/calendar/events
  CalendarConnectionStatusRow — Dataset row shape for GET /api/calendar/status

Sprint02 additions:
  CalendarCreateEventRequest  — Request body for POST /api/calendar/events
  CalendarCreateEventResult   — Success response for POST /api/calendar/events

Token fields (access_token, refresh_token) are never included here.
"""
from typing import Optional

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
# Sprint02 additions — write capability
# ---------------------------------------------------------------------------

class CalendarCreateEventRequest(BaseModel):
    """Request body for POST /api/calendar/events.

    title, start_at, end_at are required.
    description, location, all_day are optional.
    calendar_id is NOT accepted — target calendar is always operator-configured.
    """

    title: str
    start_at: str                    # ISO8601 datetime string (or YYYY-MM-DD if all_day=True)
    end_at: str                      # ISO8601 datetime string (or YYYY-MM-DD if all_day=True)
    description: Optional[str] = None
    location: Optional[str] = None
    all_day: bool = False            # if True, use date-only format in Google API call


class CalendarCreateEventResult(BaseModel):
    """Success response for POST /api/calendar/events.

    Not a Dataset row — this is a direct JSON success payload.
    Returned as JSONResponse with status_code=201.
    """

    status: str = "created"          # always 'created'
    google_event_id: str             # Google Calendar event id
    title: str
    start_at: str                    # ISO8601 string as returned by Google
    end_at: str                      # ISO8601 string as returned by Google
    all_day: bool                    # native bool (not string — this is not a Dataset row)
    source_calendar_id: str          # the target calendar ID used
    source_calendar_label: Optional[str]  # calendar summary from Google response, if available
