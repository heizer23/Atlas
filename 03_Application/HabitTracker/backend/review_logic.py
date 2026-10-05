"""
The canonical day-model/merge/expected-set/period-boundary module — the
single source of truth for every piece of "real logic" in this app.

Imported by backend/routers/reviews.py and backend/routers/reports.py. No
HTTP concerns in this file — every function here takes a cursor/connection
and plain Python values, and returns plain Python values (dicts/sets/tuples),
never a Response.

10_architecture.json internal_flow steps 6/7/8/9/10 map onto the five public
functions below, in that order.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")


def berlin_today() -> date:
    """Today's calendar date in Europe/Berlin (R-CON-AL-06). No DB access."""
    return datetime.now(BERLIN).date()


def resolve_active_habits_for_date(cur: Any, target_date: date) -> list[dict]:
    """internal_flow step 6. The single canonical query for 'habits whose
    active window covers this date' — habit.active_from <= date AND
    (habit.end_date IS NULL OR date <= habit.end_date), display_order asc.
    """
    cur.execute(
        """
        select * from habittracker.habits
        where active_from <= %s and (end_date is null or %s <= end_date)
        order by display_order asc
        """,
        (target_date, target_date),
    )
    return [dict(r) for r in cur.fetchall()]


def _habit_entry(habit_id: Any, name: str, description: str | None, display_order: int, checked: bool) -> dict:
    return {
        "habit_id": str(habit_id),
        "name": name,
        "description": description,
        "display_order": display_order,
        "checked": checked,
    }


def get_review_view(cur: Any, target_date: date) -> dict:
    """internal_flow step 7. Builds the full merged-or-frozen response shape
    for a date. Reused verbatim by both GET /reviews/{date} and PUT's
    response construction (via upsert_review below).
    """
    cur.execute("select * from habittracker.daily_reviews where review_date = %s", (target_date,))
    review_row = cur.fetchone()

    if review_row is None:
        habits = [
            _habit_entry(h["id"], h["name"], h["description"], h["display_order"], h["default_checked"])
            for h in resolve_active_habits_for_date(cur, target_date)
        ]
        return {
            "id": target_date.isoformat(),
            "review_date": target_date.isoformat(),
            "status": "unreviewed",
            "confirmed_at": None,
            "habits": habits,
        }

    status = review_row["status"]
    confirmed_at = review_row["confirmed_at"].isoformat() if review_row["confirmed_at"] else None

    if status == "confirmed":
        # Frozen set: exactly the saved habit_results rows for this date,
        # joined to each habit's CURRENT name/description for display only —
        # never recomputed from current habit active-window state.
        cur.execute(
            """
            select hr.habit_id, h.name, h.description, h.display_order, hr.checked
            from habittracker.habit_results hr
            join habittracker.habits h on h.id = hr.habit_id
            where hr.review_date = %s
            order by h.display_order asc
            """,
            (target_date,),
        )
        habits = [
            _habit_entry(r["habit_id"], r["name"], r["description"], r["display_order"], r["checked"])
            for r in cur.fetchall()
        ]
        return {
            "id": target_date.isoformat(),
            "review_date": target_date.isoformat(),
            "status": "confirmed",
            "confirmed_at": confirmed_at,
            "habits": habits,
        }

    # status == "draft": merge current active-window habits with any
    # already-saved habit_results rows for this date.
    active_habits = resolve_active_habits_for_date(cur, target_date)
    cur.execute(
        "select habit_id, checked from habittracker.habit_results where review_date = %s",
        (target_date,),
    )
    saved = {str(r["habit_id"]): r["checked"] for r in cur.fetchall()}

    habits = []
    for h in active_habits:
        habit_id = str(h["id"])
        checked = saved[habit_id] if habit_id in saved else h["default_checked"]
        habits.append(_habit_entry(h["id"], h["name"], h["description"], h["display_order"], checked))

    return {
        "id": target_date.isoformat(),
        "review_date": target_date.isoformat(),
        "status": "draft",
        "confirmed_at": confirmed_at,
        "habits": habits,
    }


def compute_expected_habit_ids(cur: Any, target_date: date) -> set[str]:
    """internal_flow step 8. The frozen-vs-active-window branching rule
    PUT /reviews/{date} validates its body against: if the day's row exists
    AND its status is 'confirmed' BEFORE the PUT call, the expected set is
    the habit_ids currently present in habit_results for that date (the
    frozen set). Otherwise (no row yet, or row exists with status='draft'),
    the expected set is resolve_active_habits_for_date(target_date) computed
    fresh.
    """
    cur.execute("select status from habittracker.daily_reviews where review_date = %s", (target_date,))
    row = cur.fetchone()

    if row is not None and row["status"] == "confirmed":
        cur.execute(
            "select habit_id from habittracker.habit_results where review_date = %s",
            (target_date,),
        )
        return {str(r["habit_id"]) for r in cur.fetchall()}

    return {str(h["id"]) for h in resolve_active_habits_for_date(cur, target_date)}


def upsert_review(conn: Any, target_date: date, status: str, habit_results: list[dict]) -> dict:
    """internal_flow step 9. Upserts the daily_reviews row (by unique
    review_date) and the habit_results rows (by unique (review_date,
    habit_id)) in one transaction, then returns get_review_view(target_date)
    as the response. Idempotent — repeating the identical call never creates
    duplicate rows. Setting status='confirmed' always stamps confirmed_at =
    now(); setting status='draft' leaves confirmed_at exactly as it was.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into habittracker.daily_reviews (review_date, status, confirmed_at)
            values (%s, %s, case when %s = 'confirmed' then now() else null end)
            on conflict (review_date) do update set
                status = excluded.status,
                confirmed_at = case when excluded.status = 'confirmed' then now()
                                     else habittracker.daily_reviews.confirmed_at end,
                updated_at = now()
            """,
            (target_date, status, status),
        )
        for hr in habit_results:
            cur.execute(
                """
                insert into habittracker.habit_results (review_date, habit_id, checked, source)
                values (%s, %s, %s, 'manual')
                on conflict (review_date, habit_id) do update set
                    checked = excluded.checked,
                    updated_at = now()
                """,
                (target_date, hr["habit_id"], hr["checked"]),
            )
    conn.commit()

    with conn.cursor() as cur:
        return get_review_view(cur, target_date)


def resolve_report_period(period: str, anchor_date: date) -> tuple[date, date, list[str]]:
    """internal_flow step 10. Pure date-range arithmetic, no I/O.
    week  -> Monday-Sunday (ISO week) containing anchor_date.
    month -> the calendar month containing anchor_date.
    Returns (period_start, period_end, dates) where dates is the full
    ordered list of YYYY-MM-DD strings from period_start to period_end
    inclusive.
    """
    if period == "week":
        period_start = anchor_date - timedelta(days=anchor_date.isoweekday() - 1)
        period_end = period_start + timedelta(days=6)
    else:
        period_start = anchor_date.replace(day=1)
        if period_start.month == 12:
            next_month_start = period_start.replace(year=period_start.year + 1, month=1)
        else:
            next_month_start = period_start.replace(month=period_start.month + 1)
        period_end = next_month_start - timedelta(days=1)

    dates: list[str] = []
    d = period_start
    while d <= period_end:
        dates.append(d.isoformat())
        d += timedelta(days=1)

    return period_start, period_end, dates
