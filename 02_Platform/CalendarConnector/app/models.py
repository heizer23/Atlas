"""
Pydantic models for the normalized CalendarEventRow and CalendarConnectionStatusRow shapes.

These are the shared_views types declared in architecture.json.
They populate Dataset rows returned by the calendar endpoints.
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
