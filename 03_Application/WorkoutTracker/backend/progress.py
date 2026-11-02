"""Activity-day statistics and streak ranking (pure functions, no I/O).

An activity day is a distinct local calendar date with qualifying completed activity
(strength session or a lighter movement day). Everything here is derived from a set of dates,
so edits, deletions and backdated entries are always reflected by simply recomputing.
"""

import calendar
import datetime as dt
from typing import Any

CHAMPIONS_MIN = 10   # streak length that qualifies for the Champions League
YEARS_SHOWN = 3      # current year + up to two earlier years in the monthly chart


def _iso(d: dt.date) -> str:
    return d.isoformat()


def find_streaks(days: set[dt.date], today: dt.date) -> list[dict[str, Any]]:
    """Maximal runs of consecutive dates. A run ending today or yesterday is the current streak."""
    runs: list[dict[str, Any]] = []
    start = prev = None
    for d in sorted(days):
        if prev is not None and d == prev + dt.timedelta(days=1):
            prev = d
            continue
        if start is not None:
            runs.append({"start": start, "end": prev})
        start = prev = d
    if start is not None:
        runs.append({"start": start, "end": prev})
    for r in runs:
        r["length"] = (r["end"] - r["start"]).days + 1
        r["current"] = r["end"] >= today - dt.timedelta(days=1)
    return runs


def rank_streaks(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Longest first; the current streak wins ties; then the most recent; ranks are positional."""
    ordered = sorted(
        runs,
        key=lambda r: (-r["length"], 0 if r["current"] else 1, -r["end"].toordinal(), -r["start"].toordinal()),
    )
    return [
        {
            "rank": i + 1,
            "start": _iso(r["start"]),
            "end": _iso(r["end"]),
            "length": r["length"],
            "current": r["current"],
        }
        for i, r in enumerate(ordered)
    ]


def _touches_year(r: dict[str, Any], year: int) -> bool:
    return r["start"].year <= year <= r["end"].year


def _count_between(sorted_days: list[dt.date], lo: dt.date, hi: dt.date) -> int:
    return sum(1 for d in sorted_days if lo <= d <= hi)


def _monthly(days: set[dt.date], year: int, today: dt.date) -> list[int | None]:
    out: list[int | None] = []
    for m in range(1, 13):
        if year == today.year and m > today.month:
            out.append(None)  # future months have no data
        else:
            out.append(sum(1 for d in days if d.year == year and d.month == m))
    return out


def _frequency(days: set[dt.date], year: int, today: dt.date) -> list[float | None]:
    """Cumulative activity days / elapsed calendar days * 7, at each month end (today for the current month)."""
    jan1 = dt.date(year, 1, 1)
    ys = sorted(d for d in days if d.year == year)
    out: list[float | None] = []
    for m in range(1, 13):
        month_end = dt.date(year, m, calendar.monthrange(year, m)[1])
        if year == today.year and m > today.month:
            out.append(None)
            continue
        point = min(month_end, today) if year == today.year else month_end
        elapsed = (point - jan1).days + 1
        out.append(round(_count_between(ys, jan1, point) / elapsed * 7, 3))
    return out


def equivalent_last_year(today: dt.date) -> dt.date:
    """Same month/day one year earlier, clamped to the month length (29 Feb -> 28 Feb)."""
    y = today.year - 1
    return dt.date(y, today.month, min(today.day, calendar.monthrange(y, today.month)[1]))


def snapshot(days: set[dt.date], today: dt.date) -> dict[str, Any]:
    year = today.year
    first = min(days) if days else None
    years = [y for y in range(year - YEARS_SHOWN + 1, year + 1) if y == year or (first and first.year <= y)]

    monthly = {str(y): _monthly(days, y, today) for y in years}
    has_prev_data = bool(first and first < dt.date(year, 1, 1))
    frequency = {str(year): _frequency(days, year, today)}
    if has_prev_data:
        frequency[str(year - 1)] = _frequency(days, year - 1, today)

    month_start = dt.date(year, today.month, 1)
    count = sum(1 for d in days if month_start <= d <= today)
    through = equivalent_last_year(today)
    last_count = sum(1 for d in days if dt.date(through.year, through.month, 1) <= d <= through)

    runs = find_streaks(days, today)
    ranking = rank_streaks(runs)
    ranking_year = rank_streaks([r for r in runs if _touches_year(r, year)])
    cur = next((r for r in ranking if r["current"]), None)
    cur_year = next((r for r in ranking_year if r["current"]), None)

    return {
        "today": _iso(today),
        "years": years,
        "monthly": monthly,
        "frequency": frequency,
        "month": {
            "year": year,
            "month": today.month,
            "day": today.day,
            "count": count,
            "last_year_count": last_count if has_prev_data else None,
            "last_year_through": _iso(through),
            "ahead": count - last_count if has_prev_data else None,
        },
        "today_counts": today in days,
        "ranking": ranking,
        "ranking_year": ranking_year,
        "current": {
            "length": cur["length"] if cur else 0,
            "rank": cur["rank"] if cur else None,
            "total": len(ranking),
            "rank_year": cur_year["rank"] if cur_year else None,
            "total_year": len(ranking_year),
        },
    }


def celebration(before: set[dt.date], after: set[dt.date], event_date: dt.date, today: dt.date) -> dict[str, Any] | None:
    """Before/after snapshots for a completion on `event_date`.

    Only a completion dated today is rewarded: backdated entries change history, not progress,
    so they get no celebration (statistics still recompute because they are derived).
    """
    if event_date != today:
        return None
    b, a = snapshot(before, today), snapshot(after, today)
    changed = today not in before and today in after
    bc, ac = b["current"], a["current"]
    return {
        "before": b,
        "after": a,
        "changed": changed,
        "note": None if changed else "Today already counts.",
        "crossed_champions": changed and bc["length"] < CHAMPIONS_MIN <= ac["length"],
    }
