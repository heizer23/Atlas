"""
Google Calendar API v3 client.

Sprint01: fetch_events() — reads events from primary calendar.
Sprint02: create_event() — inserts an event into a configured target calendar.

Both functions use httpx and return normalized internal models.
"""
import logging
from typing import Optional

import httpx

from app.models import CalendarCreateEventRequest, CalendarCreateEventResult, CalendarEventRow

log = logging.getLogger("calendar_connector")

_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_EVENTS_INSERT_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
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


def create_event(
    access_token: str,
    target_calendar_id: str,
    request: CalendarCreateEventRequest,
) -> CalendarCreateEventResult:
    """Insert a new event into the given Google Calendar using the Calendar API v3 events.insert.

    If request.all_day is True, use date-only format (YYYY-MM-DD) for start and end.
    If request.all_day is False (default), use dateTime format.

    Returns CalendarCreateEventResult on success.
    Raises ValueError on non-2xx response from Google.
    """
    if request.all_day:
        # Google requires date-only string for all-day events
        # Accept both "YYYY-MM-DD" and ISO8601 datetime — truncate to date portion
        start_date = request.start_at[:10]
        end_date = request.end_at[:10]
        start_field = {"date": start_date}
        end_field = {"date": end_date}
    else:
        # Ensure RFC3339 timezone suffix for timed events
        def _rfc3339(dt: str) -> str:
            return dt if (dt.endswith("Z") or "+" in dt[10:] or dt.count("-") > 2) else dt + "Z"

        start_field = {"dateTime": _rfc3339(request.start_at)}
        end_field = {"dateTime": _rfc3339(request.end_at)}

    body: dict = {
        "summary": request.title,
        "start": start_field,
        "end": end_field,
    }
    if request.description is not None:
        body["description"] = request.description
    if request.location is not None:
        body["location"] = request.location

    url = _EVENTS_INSERT_URL.format(calendar_id=target_calendar_id)
    log.info("Creating event in calendar=%s title=%r all_day=%s", target_calendar_id, request.title, request.all_day)

    response = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=20.0,
    )

    if response.status_code not in (200, 201):
        body_text = response.text[:500]
        raise ValueError(
            f"Google Calendar API returned {response.status_code} on events.insert: {body_text}"
        )

    data = response.json()

    # Normalize the response
    start_resp = data.get("start", {})
    end_resp = data.get("end", {})
    all_day_resp = "date" in start_resp and "dateTime" not in start_resp
    start_at_resp = start_resp.get("dateTime") or start_resp.get("date") or ""
    end_at_resp = end_resp.get("dateTime") or end_resp.get("date") or ""
    calendar_label: Optional[str] = data.get("organizer", {}).get("displayName") or None

    log.info("Event created: google_event_id=%s calendar=%s", data.get("id"), target_calendar_id)

    return CalendarCreateEventResult(
        status="created",
        google_event_id=data.get("id", ""),
        title=data.get("summary", request.title),
        start_at=start_at_resp,
        end_at=end_at_resp,
        all_day=all_day_resp,
        source_calendar_id=target_calendar_id,
        source_calendar_label=calendar_label,
    )
