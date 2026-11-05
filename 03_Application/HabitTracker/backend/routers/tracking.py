"""
Everyday tracking: one-tap logging, undo, and day-level history.

  GET    /today?date=            -> active habits with today's total / done flag
  POST   /habits/{id}/entries    -> log one tap (binary: idempotent per day)
  DELETE /habits/{id}/entries/last?date= -> undo the newest tap that day
  GET    /history?days=&end=&category_id= -> per day: habits done / habits tracked (optionally one category)
  GET    /category-progress?days=&end=&category_id= -> per category, per day: level 0..3 (null = no habit active)

A manual habit counts as done on a day if it has a habit_entries row OR a legacy
habit_results row with checked = true (the earlier evening-review data), so
history stays continuous. A linked habit (habits.source set) is done iff
EssayCards reports activity that day; it can't be logged or undone here. "Tracked" = habit's active window covers the day.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import essaycards_activity
from backend.category_progress import category_levels
from backend.database import get_db
from backend.review_logic import berlin_today
from platform_errorhandling import api_error

router = APIRouter(prefix="/habittracker", tags=["habittracker"])

MAX_HISTORY_DAYS = 90


class EntryCreate(BaseModel):
    date: str | None = None


def _parse(value: str | None) -> date | None:
    if value is None:
        return berlin_today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _categories(cur) -> list[dict]:
    cur.execute("select id::text as id, name, kind from habittracker.habit_categories order by display_order, name")
    return [dict(r) for r in cur.fetchall()]


def _habit_day_matrix(cur, start: date, end_day: date) -> list[dict]:
    """One row per (habit, day) in [start, end]: active window flag + done flag (entry, legacy
    checked result, or linked EssayCards activity). Single definition of "done" for history views."""
    linked = {k: sorted(v) for k, v in essaycards_activity.done_days(start, end_day).items()}
    cur.execute(
        """
        select h.id::text as habit_id, h.category_id::text as category_id, h.priority,
                d::date as day,
                (h.active_from <= d::date and (h.end_date is null or d::date <= h.end_date)) as active,
                (exists (select 1 from habittracker.habit_entries e
                         where e.habit_id = h.id and e.entry_date = d::date)
                 or exists (select 1 from habittracker.habit_results r
                            where r.habit_id = h.id and r.review_date = d::date and r.checked)
                 or (h.source = 'essaycards_flashcards' and d::date = any(%s::date[]))
                 or (h.source = 'essaycards_oral' and d::date = any(%s::date[]))) as done
        from habittracker.habits h
        cross join generate_series(%s::date, %s::date, interval '1 day') d
        order by h.id, d
        """,
        (linked["essaycards_flashcards"], linked["essaycards_oral"], start, end_day),
    )
    return cur.fetchall()


def _day_state(cur, habit_id: str, day: date) -> dict:
    cur.execute(
        "select coalesce(sum(amount), 0) as total from habittracker.habit_entries "
        "where habit_id = %s and entry_date = %s",
        (habit_id, day),
    )
    return {"habit_id": habit_id, "date": day.isoformat(), "total": int(cur.fetchone()["total"])}


@router.get("/today", response_model=None)
def get_today(date: str | None = None) -> JSONResponse:
    day = _parse(date)
    if day is None:
        return api_error("VALIDATION_ERROR", "date must be YYYY-MM-DD", status=400)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select h.id, h.name, h.kind, h.source, h.unit, h.increment, h.category_id, h.priority,
                       coalesce(sum(e.amount), 0) as total,
                       bool_or(r.checked) as legacy_checked
                from habittracker.habits h
                left join habittracker.habit_entries e on e.habit_id = h.id and e.entry_date = %s
                left join habittracker.habit_results r on r.habit_id = h.id and r.review_date = %s
                where h.active_from <= %s and (h.end_date is null or %s <= h.end_date)
                group by h.id
                order by h.display_order
                """,
                (day, day, day, day),
            )
            habit_rows = cur.fetchall()
            categories = _categories(cur)
            cur.execute("select level, label from habittracker.habit_priorities order by level")
            priorities = [dict(r) for r in cur.fetchall()]
    linked = essaycards_activity.done_days(day, day) if any(r["source"] for r in habit_rows) else {}
    rows = [
        {
            "habit_id": str(r["id"]), "name": r["name"], "kind": r["kind"], "linked": bool(r["source"]),
            "unit": r["unit"], "increment": r["increment"], "total": int(r["total"]),
            "category_id": str(r["category_id"]) if r["category_id"] else None, "priority": r["priority"],
            "done": (day.isoformat() in linked.get(r["source"], set())) if r["source"]
                    else int(r["total"]) > 0 or bool(r["legacy_checked"]),
        }
        for r in habit_rows
    ]
    levels = category_levels(categories, rows)
    return JSONResponse({
        "date": day.isoformat(), "habits": rows, "priorities": priorities,
        "categories": [{**c, "level": levels[c["id"]]} for c in categories],
    })


@router.post("/habits/{habit_id}/entries", response_model=None)
def log_entry(habit_id: str, body: EntryCreate) -> JSONResponse:
    day = _parse(body.date)
    if day is None:
        return api_error("VALIDATION_ERROR", "date must be YYYY-MM-DD", status=400)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select kind, increment, source from habittracker.habits where id = %s", (habit_id,))
            habit = cur.fetchone()
            if not habit:
                return api_error("NOT_FOUND", f"Habit {habit_id} not found", status=404)
            if habit["source"]:
                return api_error("VALIDATION_ERROR", "Linked habits are tracked automatically", status=400)
            state = _day_state(cur, habit_id, day)
            if habit["kind"] == "binary" and state["total"] > 0:
                return JSONResponse(state)  # already done today; idempotent
            cur.execute(
                "insert into habittracker.habit_entries (habit_id, entry_date, amount) values (%s, %s, %s)",
                (habit_id, day, habit["increment"] if habit["kind"] == "quantity" else 1),
            )
            state = _day_state(cur, habit_id, day)
        conn.commit()
    return JSONResponse(state, status_code=201)


@router.delete("/habits/{habit_id}/entries/last", response_model=None)
def undo_entry(habit_id: str, date: str | None = None) -> JSONResponse:
    day = _parse(date)
    if day is None:
        return api_error("VALIDATION_ERROR", "date must be YYYY-MM-DD", status=400)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select source from habittracker.habits where id = %s", (habit_id,))
            habit = cur.fetchone()
            if not habit:
                return api_error("NOT_FOUND", f"Habit {habit_id} not found", status=404)
            if habit["source"]:
                return api_error("VALIDATION_ERROR", "Linked habits are tracked automatically", status=400)
            cur.execute(
                """
                delete from habittracker.habit_entries where id = (
                    select id from habittracker.habit_entries
                    where habit_id = %s and entry_date = %s
                    order by created_at desc, id limit 1)
                """,
                (habit_id, day),
            )
            state = _day_state(cur, habit_id, day)
        conn.commit()
    return JSONResponse(state)


@router.get("/history", response_model=None)
def get_history(days: int = 28, end: str | None = None, category_id: str | None = None) -> JSONResponse:
    end_day = _parse(end)
    if end_day is None or not 1 <= days <= MAX_HISTORY_DAYS:
        return api_error("VALIDATION_ERROR", f"end must be YYYY-MM-DD and days 1..{MAX_HISTORY_DAYS}", status=400)
    start = end_day - timedelta(days=days - 1)
    linked = {k: sorted(v) for k, v in essaycards_activity.done_days(start, end_day).items()}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select d::date as day,
                  (select count(*) from habittracker.habits h
                    where h.active_from <= d::date and (h.end_date is null or d::date <= h.end_date)
                      and (%s::text is null or h.category_id::text = %s)) as tracked,
                  (select count(*) from habittracker.habits h
                    where h.active_from <= d::date and (h.end_date is null or d::date <= h.end_date)
                      and (%s::text is null or h.category_id::text = %s)
                      and (exists (select 1 from habittracker.habit_entries e
                                   where e.habit_id = h.id and e.entry_date = d::date)
                           or exists (select 1 from habittracker.habit_results r
                                      where r.habit_id = h.id and r.review_date = d::date and r.checked)
                           or (h.source = 'essaycards_flashcards' and d::date = any(%s::date[]))
                           or (h.source = 'essaycards_oral' and d::date = any(%s::date[])))) as done
                from generate_series(%s::date, %s::date, interval '1 day') d
                order by d
                """,
                (category_id, category_id, category_id, category_id,
                 linked["essaycards_flashcards"], linked["essaycards_oral"], start, end_day),
            )
            rows = [{"date": r["day"].isoformat(), "done": int(r["done"]), "tracked": int(r["tracked"])}
                    for r in cur.fetchall()]
    return JSONResponse({"days": rows})


@router.get("/habit-history", response_model=None)
def get_habit_history(days: int = 28, end: str | None = None) -> JSONResponse:
    """Per habit, per day: 1 done, 0 open, null outside the habit's active window."""
    end_day = _parse(end)
    if end_day is None or not 1 <= days <= MAX_HISTORY_DAYS:
        return api_error("VALIDATION_ERROR", f"end must be YYYY-MM-DD and days 1..{MAX_HISTORY_DAYS}", status=400)
    start = end_day - timedelta(days=days - 1)
    with get_db() as conn:
        with conn.cursor() as cur:
            matrix = _habit_day_matrix(cur, start, end_day)
    out: dict[str, list] = {}
    for r in matrix:
        out.setdefault(r["habit_id"], []).append(None if not r["active"] else (1 if r["done"] else 0))
    return JSONResponse({"end": end_day.isoformat(), "days": days, "habits": out})


@router.get("/category-progress", response_model=None)
def get_category_progress(days: int = 28, end: str | None = None, category_id: str | None = None) -> JSONResponse:
    """Per category, oldest-first list of daily levels: 0..max priority, null = no habit of the
    category active that day. Levels are derived (category_progress.category_levels), not stored.
    `categories` are returned in display order; `category_id` limits to one."""
    end_day = _parse(end)
    if end_day is None or not 1 <= days <= MAX_HISTORY_DAYS:
        return api_error("VALIDATION_ERROR", f"end must be YYYY-MM-DD and days 1..{MAX_HISTORY_DAYS}", status=400)
    start = end_day - timedelta(days=days - 1)
    with get_db() as conn:
        with conn.cursor() as cur:
            categories = _categories(cur)
            matrix = _habit_day_matrix(cur, start, end_day)
    if category_id is not None:
        categories = [c for c in categories if c["id"] == category_id]
        if not categories:
            return api_error("NOT_FOUND", f"Category {category_id} not found", status=404)
    by_day: dict[date, list[dict]] = {}
    for r in matrix:
        if r["active"]:
            by_day.setdefault(r["day"], []).append(r)
    dates = [start + timedelta(days=i) for i in range(days)]
    per_day = [category_levels(categories, by_day.get(d, [])) for d in dates]
    return JSONResponse({
        "end": end_day.isoformat(), "days": days, "dates": [d.isoformat() for d in dates],
        "categories": [{**c, "levels": [lv[c["id"]] for lv in per_day]} for c in categories],
    })
