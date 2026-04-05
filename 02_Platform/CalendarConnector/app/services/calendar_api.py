"""
Google Calendar API v3 client.

Sprint01: fetch_events() — reads events from primary calendar.
Sprint02: create_event() — inserts an event into a configured target calendar.
Sprint03: update_event() — patches an existing event via atlas_event_id lookup.
          delete_event() — deletes an event; distinguishes 404 (idempotent) from other errors.
          create_event() retrofitted to inject extendedProperties.private.atlas_event_id.

All functions use httpx and return normalized internal models.
"""
import logging
from typing import Optional

import httpx

from app.models import (
    CalendarCreateEventRequest,
    CalendarEventOperationResult,
    CalendarEventRow,
    CalendarUpdateEventRequest,
)

log = logging.getLogger("calendar_connector")

_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_EVENTS_INSERT_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
_EVENTS_PATCH_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
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


def _rfc3339(dt: str) -> str:
    """Append Z to a datetime string if no timezone offset is present."""
    return dt if (dt.endswith("Z") or "+" in dt[10:] or dt.count("-") > 2) else dt + "Z"


def create_event(
    access_token: str,
    target_calendar_id: str,
    request: CalendarCreateEventRequest,
) -> CalendarEventOperationResult:
    """Insert a new event into the given Google Calendar using the Calendar API v3 events.insert.

    If request.all_day is True, use date-only format (YYYY-MM-DD) for start and end.
    If request.all_day is False (default), use dateTime format.

    Sprint03 retrofit: includes extendedProperties.private.atlas_event_id in the request body
    so the Atlas stable identity is stored on the Google event itself.

    Returns CalendarEventOperationResult with status='created' on success.
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
        start_field = {"dateTime": _rfc3339(request.start_at)}
        end_field = {"dateTime": _rfc3339(request.end_at)}

    body: dict = {
        "summary": request.title,
        "start": start_field,
        "end": end_field,
        # Store the Atlas stable ID on the Google event for traceability
        "extendedProperties": {
            "private": {"atlas_event_id": request.atlas_event_id}
        },
    }
    if request.description is not None:
        body["description"] = request.description
    if request.location is not None:
        body["location"] = request.location

    url = _EVENTS_INSERT_URL.format(calendar_id=target_calendar_id)
    log.info(
        "Creating event in calendar=%s title=%r all_day=%s atlas_event_id=%s",
        target_calendar_id,
        request.title,
        request.all_day,
        request.atlas_event_id,
    )

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

    return CalendarEventOperationResult(
        status="created",
        atlas_event_id=request.atlas_event_id,
        google_event_id=data.get("id", ""),
        title=data.get("summary", request.title),
        start_at=start_at_resp,
        end_at=end_at_resp,
        all_day=all_day_resp,
        source_calendar_id=target_calendar_id,
        source_calendar_label=calendar_label,
    )


class GoogleEventNotFoundError(ValueError):
    """Raised by update_event when Google returns 404 for the target event.

    This is a distinct subclass of ValueError so the router can distinguish a missing
    event (which drives index status='error') from other Google API failures.
    """


def update_event(
    access_token: str,
    target_calendar_id: str,
    google_event_id: str,
    request: CalendarUpdateEventRequest,
    atlas_event_id: str,
) -> CalendarEventOperationResult:
    """Patch an existing Google Calendar event using the Calendar API v3 events.patch.

    Only fields present in request (non-None) are sent in the patch body.
    extendedProperties.private.atlas_event_id is always re-sent to preserve metadata.

    Returns CalendarEventOperationResult with status='updated' on success.
    Raises GoogleEventNotFoundError if Google returns 404.
    Raises ValueError on other non-2xx responses.
    """
    patch_body: dict = {
        # Always preserve the Atlas stable ID on the Google event
        "extendedProperties": {
            "private": {"atlas_event_id": atlas_event_id}
        },
    }

    if request.title is not None:
        patch_body["summary"] = request.title

    if request.all_day is not None:
        all_day = request.all_day
    else:
        # We don't know the current all_day state — infer from provided dates if both given
        # If not provided, omit date fields entirely (Google keeps existing values)
        all_day = False

    if request.start_at is not None or request.end_at is not None:
        if request.all_day is True:
            if request.start_at is not None:
                patch_body["start"] = {"date": request.start_at[:10]}
            if request.end_at is not None:
                patch_body["end"] = {"date": request.end_at[:10]}
        else:
            if request.start_at is not None:
                patch_body["start"] = {"dateTime": _rfc3339(request.start_at)}
            if request.end_at is not None:
                patch_body["end"] = {"dateTime": _rfc3339(request.end_at)}

    if request.description is not None:
        patch_body["description"] = request.description
    if request.location is not None:
        patch_body["location"] = request.location

    url = _EVENTS_PATCH_URL.format(
        calendar_id=target_calendar_id,
        event_id=google_event_id,
    )
    log.info(
        "Updating event: google_event_id=%s atlas_event_id=%s calendar=%s",
        google_event_id,
        atlas_event_id,
        target_calendar_id,
    )

    response = httpx.patch(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=patch_body,
        timeout=20.0,
    )

    if response.status_code == 404:
        raise GoogleEventNotFoundError(
            f"Google event {google_event_id!r} not found (404) during update"
        )

    if response.status_code not in (200, 201):
        body_text = response.text[:500]
        raise ValueError(
            f"Google Calendar API returned {response.status_code} on events.patch: {body_text}"
        )

    data = response.json()

    start_resp = data.get("start", {})
    end_resp = data.get("end", {})
    all_day_resp = "date" in start_resp and "dateTime" not in start_resp
    start_at_resp = start_resp.get("dateTime") or start_resp.get("date") or ""
    end_at_resp = end_resp.get("dateTime") or end_resp.get("date") or ""
    calendar_label: Optional[str] = data.get("organizer", {}).get("displayName") or None

    log.info("Event updated: google_event_id=%s atlas_event_id=%s", google_event_id, atlas_event_id)

    return CalendarEventOperationResult(
        status="updated",
        atlas_event_id=atlas_event_id,
        google_event_id=data.get("id", google_event_id),
        title=data.get("summary", ""),
        start_at=start_at_resp,
        end_at=end_at_resp,
        all_day=all_day_resp,
        source_calendar_id=target_calendar_id,
        source_calendar_label=calendar_label,
    )


def delete_event(
    access_token: str,
    target_calendar_id: str,
    google_event_id: str,
) -> bool:
    """Delete a Google Calendar event using the Calendar API v3 events.delete.

    Returns True on 204 (successful deletion).
    Returns False on 404 (event already absent — idempotent case).
    Raises ValueError on other non-2xx responses.
    """
    url = _EVENTS_PATCH_URL.format(
        calendar_id=target_calendar_id,
        event_id=google_event_id,
    )
    log.info(
        "Deleting event: google_event_id=%s calendar=%s",
        google_event_id,
        target_calendar_id,
    )

    response = httpx.delete(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20.0,
    )

    if response.status_code == 204:
        log.info("Event deleted: google_event_id=%s", google_event_id)
        return True

    if response.status_code == 404:
        log.info("Event already absent (404): google_event_id=%s", google_event_id)
        return False

    body_text = response.text[:500]
    raise ValueError(
        f"Google Calendar API returned {response.status_code} on events.delete: {body_text}"
    )
