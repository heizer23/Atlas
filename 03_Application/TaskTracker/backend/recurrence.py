"""Pure, DB-free recurrence helpers (Sprint11). Authoritative next-date rule."""

import calendar
from datetime import date, timedelta

VALID_RECURRENCE_FREQ = {"daily", "weekly", "monthly"}
VALID_RECURRENCE_MODE = {"fixed", "after_completion"}


def add_months(d: date, months: int) -> date:
    """Shift d by months calendar months; clamp day to the target month's last day."""
    idx = d.year * 12 + (d.month - 1) + months
    year, month = divmod(idx, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def advance_date(anchor: date, freq: str, interval: int, steps: int) -> date:
    """anchor advanced by steps*interval units, always measured from anchor."""
    n = steps * interval
    if freq == "daily":
        return anchor + timedelta(days=n)
    if freq == "weekly":
        return anchor + timedelta(days=7 * n)
    if freq == "monthly":
        return add_months(anchor, n)
    raise ValueError(f"unknown recurrence freq: {freq}")


def compute_next_date(anchor: "date | None", freq: str, interval: int, mode: str, today: date) -> date:
    """Next occurrence date; always strictly greater than today."""
    if mode == "after_completion" or anchor is None:
        return advance_date(today, freq, interval, 1)
    steps = 1
    while True:
        nxt = advance_date(anchor, freq, interval, steps)
        if nxt > today:
            return nxt
        steps += 1


def format_recurrence_label(freq: "str | None", interval: int, mode: str) -> "str | None":
    if freq is None:
        return None
    if interval == 1:
        label = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}[freq]
    else:
        unit = {"daily": "days", "weekly": "weeks", "monthly": "months"}[freq]
        label = f"Every {interval} {unit}"
    if mode == "after_completion":
        label += ", after completion"
    return label
