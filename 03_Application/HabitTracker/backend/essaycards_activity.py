"""
Read-only client for EssayCards' GET /activity (the authoritative source for
linked habits). EssayCards owns the data and the Berlin-day bucketing; this
module only fetches. Any failure returns None/empty so Habits keeps working
with linked habits simply showing as not done.
"""

from __future__ import annotations

import logging
import os
from datetime import date

import httpx

log = logging.getLogger("habittracker")

# habit.source -> key in the EssayCards payload
KEYS = {"essaycards_flashcards": "flashcards", "essaycards_oral": "oral"}


def _fetch(start: date, end: date) -> dict | None:
    url = os.environ.get("ESSAYCARDS_URL", "http://atlas-essaycards:8000")
    try:
        r = httpx.get(f"{url}/api/essaycards/activity",
                      params={"start": start.isoformat(), "end": end.isoformat()}, timeout=3.0)
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001 — degrade, never break Habits
        log.warning("EssayCards activity unavailable: %s", exc)
        return None


def done_days(start: date, end: date) -> dict[str, set[str]]:
    """{habit.source: {ISO dates with activity}} for start..end inclusive."""
    payload = _fetch(start, end)
    out: dict[str, set[str]] = {src: set() for src in KEYS}
    if payload:
        for d in payload["days"]:
            for src, key in KEYS.items():
                if d[key]:
                    out[src].add(d["date"])
    return out


def first_day(source: str) -> date | None:
    """Earliest day EssayCards has activity of this kind (None if none/unreachable)."""
    payload = _fetch(date.today(), date.today())
    first = (payload or {}).get("first", {}).get(KEYS[source])
    return date.fromisoformat(first) if first else None
