"""
GET /activity?start=YYYY-MM-DD&end=YYYY-MM-DD — per-day "did the learner make an
effort" flags, consumed read-only by HabitTracker (linked habits).

Effort only, never volume or score:
  flashcards — a review_events row (one is written per genuine review; a
               revalidation-correct answer writes none and opening the app
               writes none).
  oral       — a guided learning session, or a section/essay examination
               (guided or unguided), or a recall review.
Days are Europe/Berlin calendar days (the Habits day boundary), not UTC.
`first` is the earliest day with any such activity per kind (null if none), so
a consumer can start its history where reliable records begin.
"""

from datetime import date, timedelta

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database import get_db
from platform_errorhandling import api_error

router = APIRouter(prefix="/activity", tags=["activity"])

MAX_SPAN_DAYS = 400
TZ = "Europe/Berlin"

_FLASHCARD_SQL = f"select (reviewed_at at time zone '{TZ}')::date as day from essaycards.review_events"
_ORAL_SQL = f"""
    select (session_at at time zone '{TZ}')::date as day from essaycards.section_guided_sessions
    union all select (examined_at at time zone '{TZ}')::date from essaycards.section_examinations
    union all select (examined_at at time zone '{TZ}')::date from essaycards.essay_examinations
    union all select (examined_at at time zone '{TZ}')::date from essaycards.recall_reviews
"""


@router.get("", response_model=None)
def get_activity(start: str, end: str) -> JSONResponse:
    try:
        start_d, end_d = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        return api_error("VALIDATION_ERROR", "start and end must be YYYY-MM-DD", status=400)
    if end_d < start_d or (end_d - start_d).days > MAX_SPAN_DAYS:
        return api_error("VALIDATION_ERROR", f"end must be on/after start, span <= {MAX_SPAN_DAYS} days", status=400)

    out: dict[str, dict] = {}
    first: dict[str, str | None] = {}
    with get_db() as conn:
        with conn.cursor() as cur:
            for key, sql in (("flashcards", _FLASHCARD_SQL), ("oral", _ORAL_SQL)):
                cur.execute(f"select min(day) as first, array_agg(distinct day) filter (where day between %s and %s) as days from ({sql}) t",
                            (start_d, end_d))
                row = cur.fetchone()
                first[key] = row["first"].isoformat() if row["first"] else None
                out[key] = {d.isoformat() for d in (row["days"] or [])}

    days = []
    d = start_d
    while d <= end_d:
        iso = d.isoformat()
        days.append({"date": iso, "flashcards": iso in out["flashcards"], "oral": iso in out["oral"]})
        d += timedelta(days=1)
    return JSONResponse({"days": days, "first": first})
