"""
Google Calendar API v3 client.

Fetches events from the primary calendar for a given time window using httpx.
Returns a list of CalendarEventRow (normalized internal shape).
"""
import logging
from typing import Optional

import httpx

from app.models import CalendarEventRow

log = logging.getLogger("calendar_connector")

_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_PRIMARY_CALENDAR_ID = "primary"


def _normalize_event(item: dict) -> CalendarEventRow:
    """Normalize a single Google Calendar event item into CalendarEventRow."""
    start = item.get("start", {})
    end = item.get("end", {})

    # Determine whether this is an all-day event (date only, no dateTime)
    all_day = "date" in start and "dateTime" not in start

    # Use dateTime for timed events, date for all-day events
    start_at = start.get("dateTime") or start.get("date") or ""
    end_at = end.get("dateTime") or end.get("date") or ""

    return CalendarEventRow(
        id=item.get("id", ""),
        title=item.get("summary", "(no title)"),
        description=item.get("description") or None,
        start_at=start_at,
        end_at=end_at,
        all_day="true" if all_day else "false",
        location=item.get("location") or None,
        status=item.get("status", "confirmed"),
        source_calendar_id=_PRIMARY_CALENDAR_ID,
        source_calendar_label=item.get("organizer", {}).get("displayName") or None,
    )


def fetch_events(access_token: str, from_dt: str, to_dt: str) -> list[CalendarEventRow]:
    """Call Google Calendar API v3 events.list for the primary calendar.

    Args:
        access_token: valid (post-refresh if needed) Google access token
        from_dt: ISO8601 datetime string for timeMin
        to_dt: ISO8601 datetime string for timeMax

    Returns:
        List of CalendarEventRow normalized from the Google response.

    Raises:
        ValueError: if Google returns a non-2xx response.
    """
    # Google requires RFC3339 with timezone — append Z if no offset present
    def _rfc3339(dt: str) -> str:
        return dt if (dt.endswith("Z") or "+" in dt[10:] or dt.count("-") > 2) else dt + "Z"

    params = {
        "timeMin": _rfc3339(from_dt),
        "timeMax": _rfc3339(to_dt),
        "singleEvents": "true",   # expand recurring events
        "orderBy": "startTime",
        "maxResults": 250,
    }
    log.info("Fetching events: timeMin=%s timeMax=%s", params["timeMin"], params["timeMax"])
    response = httpx.get(
        _EVENTS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=20.0,
    )

    if response.status_code != 200:
        body = response.text[:500]
        raise ValueError(
            f"Google Calendar API returned {response.status_code}: {body}"
        )

    data = response.json()
    items = data.get("items", [])
    log.debug("Fetched %d events from Google Calendar", len(items))
    return [_normalize_event(item) for item in items]
