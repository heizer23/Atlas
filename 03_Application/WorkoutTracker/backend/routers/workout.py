import datetime
import logging
import uuid
import zoneinfo
from typing import Any

import psycopg2.errors

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from backend.database import get_db
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/workout", tags=["workout"])
perf_log = logging.getLogger("workouttracker.perf")

# ── Schemas ───────────────────────────────────────────────────────────────────

SESSION_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="workout_date",   label="Date",      type="date",   sortable=True),
    ColumnSchema(key="split",          label="Split",     type="string", sortable=True,  filterable=True),
    ColumnSchema(key="exercise_count", label="Exercises", type="number", sortable=False),
]

# Only the fields shown in TableView / BarChart.
# set1_reps–set5_reps and comment travel in the row but are not in the schema —
# they are invisible to TableView/BarChart but available to the edit form.
EXERCISE_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="exercise",   label="Exercise",    type="string", sortable=True),
    ColumnSchema(key="weight_kg",  label="Weight (kg)", type="number", sortable=True, format="kg"),
    ColumnSchema(key="total_reps", label="Total Reps",  type="number", sortable=True),
]

# ── Request bodies ────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    workout_date: str        # ISO date string "YYYY-MM-DD"
    split:        str
    exercise:     str
    weight_kg:    float | None = None
    set1_reps:    int   | None = None
    set2_reps:    int   | None = None
    set3_reps:    int   | None = None
    set4_reps:    int   | None = None
    set5_reps:    int   | None = None
    comment:      str   | None = None


class SessionStart(BaseModel):
    split:           str
    workout_date:    str | None = None   # ISO date; defaults to the server date
    from_session_id: str | None = None   # template session; defaults to the latest session of this split
    tz:              str | None = None   # client IANA time zone (e.g. "Europe/Berlin"), stored for time-of-day analysis


class ExerciseCreate(BaseModel):
    exercise:  str
    status:    str = "done"              # "planned" = name (+ optional weight) only, no reps yet
    weight_kg: float | None = None
    set1_reps: int   | None = None
    set2_reps: int   | None = None
    set3_reps: int   | None = None
    set4_reps: int   | None = None
    set5_reps: int   | None = None
    comment:   str   | None = None


class ExerciseUpdate(BaseModel):
    exercise:  str
    weight_kg: float | None = None
    set1_reps: int   | None = None
    set2_reps: int   | None = None
    set3_reps: int   | None = None
    set4_reps: int   | None = None
    set5_reps: int   | None = None
    comment:   str   | None = None


class SetConfirm(BaseModel):
    reps:      int
    weight_kg: float | None = None       # explicit null = no weight recorded (never read as bodyweight)


class ExerciseDetails(BaseModel):
    """Name / weight / comment only. All three are always sent: null weight or comment clears it."""
    exercise:  str
    weight_kg: float | None
    comment:   str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


def _has_reps(body: ExerciseCreate | ExerciseUpdate) -> bool:
    return any(
        v is not None
        for v in (body.set1_reps, body.set2_reps, body.set3_reps, body.set4_reps, body.set5_reps)
    )


def _total_reps(row: Any) -> int:
    return sum(row[f] or 0 for f in ("set1_reps", "set2_reps", "set3_reps", "set4_reps", "set5_reps"))


def _exercise_row(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["id"]         = str(d.pop("workout_log_id"))
    d["total_reps"] = _total_reps(d)
    d["weight_kg"]  = float(d["weight_kg"]) if d.get("weight_kg") is not None else None
    for n in range(1, 6):
        for k in (f"set{n}_started_at", f"set{n}_ended_at"):
            if d.get(k) is not None:
                d[k] = d[k].isoformat()
    return d


def _exercises_dataset(rows: list[Any], session_id: str) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="workout_exercise",
            label="Exercises",
            total=len(rows),
            page=1,
            page_size=len(rows) or 1,
            row_actions=["edit", "delete"],
        ),
        **{"schema": EXERCISE_SCHEMA},
        rows=[_exercise_row(r) for r in rows],
    )


def _fetch_exercises(conn: Any, session_id: str) -> list[Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT l.workout_log_id, l.exercise, l.weight_kg, l.status,
                   l.workout_date::text AS workout_date, l.split,
                   l.set1_reps, l.set2_reps, l.set3_reps, l.set4_reps, l.set5_reps, l.comment,
                   l.set1_started_at, l.set1_ended_at, l.set2_started_at, l.set2_ended_at,
                   l.set3_started_at, l.set3_ended_at, l.set4_started_at, l.set4_ended_at,
                   l.set5_started_at, l.set5_ended_at,
                   h.delta
            FROM workout.workout_log l
            LEFT JOIN workout.exercise_session_history h ON h.id = l.workout_log_id::text
            WHERE l.workout_id = %s
            ORDER BY l.created_at ASC, l.workout_log_id ASC
            """,
            (session_id,),
        )
        return cur.fetchall()


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=None)
def list_sessions(
    page: int = 1,
    page_size: int = 25,
    split: str | None = None,
    include_active: bool = False,
    include_exercises: bool = False,
) -> JSONResponse:
    """Finished sessions, newest first (workout_date DESC, created_at DESC).

    split:          optional, case-insensitive exact match on the archetype name.
    include_active: default false; the active session is reached via the Session tab.
    include_exercises: default false; when true each row carries `exercises`, the session's
                    performed exercises in entry order (id, exercise, weight_kg, set1..5_reps,
                    delta) so the Log renders without one request per session. Read-only.
    Legacy sessions (no workout_session row) count as finished.
    Empty result: Dataset with zero rows. exercise_count counts performed exercises only.
    """
    if page < 1:
        return api_error("INVALID_PARAM", "page must be ≥ 1")

    offset = (page - 1) * page_size
    where = ["1=1"]
    args: list[Any] = []
    if split:
        where.append("LOWER(TRIM(l.split)) = LOWER(%s)")
        args.append(split.strip())
    if not include_active:
        where.append("COALESCE(s.status, 'finished') <> 'active'")
    where_sql = " AND ".join(where)

    base = f"""
        FROM workout.workout_log l
        LEFT JOIN workout.workout_session s ON s.workout_id = l.workout_id
        WHERE {where_sql}
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(DISTINCT l.workout_id) {base}", args)
            total = int(cur.fetchone()["count"])
            cur.execute(
                f"""
                SELECT
                    l.workout_id::text                            AS id,
                    MAX(l.workout_date)::text                     AS workout_date,
                    MAX(l.split)                                  AS split,
                    COUNT(*) FILTER (WHERE l.status = 'done')::int AS exercise_count,
                    COALESCE(MAX(s.status), 'finished')           AS status
                {base}
                GROUP BY l.workout_id
                ORDER BY MAX(l.workout_date) DESC, MAX(l.created_at) DESC
                LIMIT %s OFFSET %s
                """,
                (*args, page_size, offset),
            )
            rows = [dict(r) for r in cur.fetchall()]

            if include_exercises and rows:
                cur.execute(
                    """
                    SELECT l.workout_id::text AS sid, l.workout_log_id::text AS id, l.exercise,
                           l.weight_kg, l.set1_reps, l.set2_reps, l.set3_reps, l.set4_reps,
                           l.set5_reps, h.delta
                    FROM workout.workout_log l
                    LEFT JOIN workout.exercise_session_history h ON h.id = l.workout_log_id::text
                    WHERE l.workout_id = ANY(%s::uuid[]) AND l.status = 'done'
                    ORDER BY l.created_at ASC, l.workout_log_id ASC
                    """,
                    ([r["id"] for r in rows],),
                )
                grouped: dict[str, list[dict[str, Any]]] = {}
                for e in cur.fetchall():
                    d = dict(e)
                    sid = d.pop("sid")
                    d["weight_kg"] = float(d["weight_kg"]) if d["weight_kg"] is not None else None
                    grouped.setdefault(sid, []).append(d)
                for r in rows:
                    r["exercises"] = grouped.get(r["id"], [])

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="workout_session",
            label="Workout Sessions",
            total=total,
            page=page,
            page_size=page_size,
            row_actions=["delete"],
        ),
        **{"schema": SESSION_SCHEMA},
        rows=rows,
    ))


# ── Session lifecycle ─────────────────────────────────────────────────────────

ACTIVE_SESSION_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="split",        label="Split",   type="string", sortable=False),
    ColumnSchema(key="workout_date", label="Date",    type="date",   sortable=False),
    ColumnSchema(key="started_at",   label="Started", type="string", sortable=False),
]

ARCHETYPE_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="split",         label="Split",         type="string", sortable=False),
    ColumnSchema(key="session_count", label="Sessions",      type="number", sortable=False),
    ColumnSchema(key="last_date",     label="Last session",  type="date",   sortable=False),
]


def _active_dataset(rows: list[dict[str, Any]]) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type="workout_active_session",
            label="Active Session",
            total=len(rows),
            page=1,
            page_size=len(rows) or 1,
        ),
        **{"schema": ACTIVE_SESSION_SCHEMA},
        rows=rows,
    )


def _fetch_active(cur: Any) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT workout_id::text AS id, split, workout_date::text AS workout_date,
               started_at::text AS started_at
        FROM workout.workout_session
        WHERE status = 'active'
        """
    )
    return [dict(r) for r in cur.fetchall()]


@router.get("/sessions/active", response_model=None)
def active_session() -> JSONResponse:
    """The single active session, or a Dataset with zero rows when none is active."""
    with get_db() as conn:
        with conn.cursor() as cur:
            rows = _fetch_active(cur)
    return dataset_response(_active_dataset(rows))


@router.get("/archetypes", response_model=None)
def list_archetypes() -> JSONResponse:
    """Archetypes derived from the split names in use, grouped case-insensitively.

    Display name = the spelling of the most recent session. Order: most recently used first.
    Planned-only rows do not count as a use.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    (ARRAY_AGG(split ORDER BY workout_date DESC, created_at DESC))[1] AS split,
                    COUNT(DISTINCT workout_id)::int                                  AS session_count,
                    MAX(workout_date)::text                                          AS last_date
                FROM workout.workout_log
                WHERE status = 'done'
                GROUP BY LOWER(TRIM(split))
                ORDER BY MAX(workout_date) DESC, MAX(created_at) DESC
                """
            )
            rows = [{"id": r["split"], **dict(r)} for r in cur.fetchall()]

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="workout_archetype",
            label="Archetypes",
            total=len(rows),
            page=1,
            page_size=len(rows) or 1,
        ),
        **{"schema": ARCHETYPE_SCHEMA},
        rows=rows,
    ))


@router.post("/sessions/start", response_model=None)
def start_session(body: SessionStart) -> JSONResponse:
    """Start a session from an archetype (or repeat a given session).

    Creates a new session; never touches the template. Exercises and starting weights are
    copied as 'planned' rows (no reps, no comment): achieved results are not copied.
    Template: from_session_id if given, else the latest session of this split, else none.
    Time authority: workout_date is the client's local date (the server runs in UTC and would
    be off around midnight); the server date is only the fallback when the client omits it.
    Rejected with ACTIVE_SESSION_EXISTS if a session is already active.
    """
    split = body.split.strip()
    if not split:
        return api_error("VALIDATION_ERROR", "split cannot be empty")
    try:
        if body.workout_date:
            datetime.date.fromisoformat(body.workout_date)
        if body.from_session_id:
            uuid.UUID(body.from_session_id)
    except ValueError:
        return api_error("VALIDATION_ERROR", "workout_date must be YYYY-MM-DD and from_session_id a UUID")
    if body.tz:
        try:
            zoneinfo.ZoneInfo(body.tz)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            return api_error("VALIDATION_ERROR", "tz must be an IANA time zone name")

    new_id = str(uuid.uuid4())
    with get_db() as conn:
        with conn.cursor() as cur:
            if _fetch_active(cur):
                return api_error("ACTIVE_SESSION_EXISTS", "a session is already active", status=409)

            if body.from_session_id:
                cur.execute(
                    "SELECT 1 FROM workout.workout_log WHERE workout_id = %s LIMIT 1",
                    (body.from_session_id,),
                )
                if not cur.fetchone():
                    return api_error("NOT_FOUND", f"session {body.from_session_id} not found", status=404)
                template_id = body.from_session_id
            else:
                cur.execute(
                    """
                    SELECT workout_id::text AS id
                    FROM workout.workout_log
                    WHERE LOWER(TRIM(split)) = LOWER(%s) AND status = 'done'
                    ORDER BY workout_date DESC, created_at DESC
                    LIMIT 1
                    """,
                    (split,),
                )
                found = cur.fetchone()
                template_id = found["id"] if found else None

            try:
                cur.execute(
                    "INSERT INTO workout.workout_session (workout_id, split, workout_date, tz) "
                    "VALUES (%s, %s, COALESCE(%s::date, CURRENT_DATE), %s)",
                    (new_id, split, body.workout_date, body.tz or None),
                )
            except psycopg2.errors.UniqueViolation:
                # Lost a race with another start: the one-active-session index decided.
                conn.rollback()
                return api_error("ACTIVE_SESSION_EXISTS", "a session is already active", status=409)
            if template_id:
                cur.execute(
                    """
                    INSERT INTO workout.workout_log
                        (workout_id, workout_date, split, exercise, weight_kg, status)
                    SELECT %s, COALESCE(%s::date, CURRENT_DATE), %s, exercise, weight_kg, 'planned'
                    FROM workout.workout_log
                    WHERE workout_id = %s
                    ORDER BY created_at ASC, workout_log_id ASC
                    """,
                    (new_id, body.workout_date, split, template_id),
                )
            rows = _fetch_active(cur)
        conn.commit()

    return dataset_response(_active_dataset(rows))


@router.post("/sessions/{session_id}/finish", response_model=None)
def finish_session(session_id: str) -> JSONResponse:
    """Finish the active session. Exercises still 'planned' were never performed and are removed.

    If nothing was performed, the session is discarded entirely.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM workout.workout_session WHERE workout_id = %s AND status = 'active'",
                (session_id,),
            )
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"no active session {session_id}", status=404)
            cur.execute(
                "DELETE FROM workout.workout_log WHERE workout_id = %s AND status = 'planned'",
                (session_id,),
            )
            cur.execute(
                "SELECT 1 FROM workout.workout_log WHERE workout_id = %s LIMIT 1", (session_id,)
            )
            if cur.fetchone():
                cur.execute(
                    "UPDATE workout.workout_session SET status = 'finished', finished_at = NOW() "
                    "WHERE workout_id = %s",
                    (session_id,),
                )
            else:
                cur.execute("DELETE FROM workout.workout_session WHERE workout_id = %s", (session_id,))
        conn.commit()

    return dataset_response(_active_dataset([]))


@router.post("/sessions", response_model=None)
def create_session(body: SessionCreate) -> JSONResponse:
    if not body.split.strip():
        return api_error("VALIDATION_ERROR", "split cannot be empty")
    if not body.exercise.strip():
        return api_error("VALIDATION_ERROR", "exercise cannot be empty")
    if not _has_reps(body):
        return api_error("VALIDATION_ERROR", "at least one set must have reps")

    session_id = str(uuid.uuid4())

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workout.workout_log (
                    workout_id, workout_date, split, exercise, weight_kg,
                    set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id, body.workout_date, body.split.strip(), body.exercise.strip(),
                    body.weight_kg,
                    body.set1_reps, body.set2_reps, body.set3_reps, body.set4_reps, body.set5_reps,
                    body.comment,
                ),
            )
        conn.commit()

    with get_db() as conn:
        rows = _fetch_exercises(conn, session_id)

    return dataset_response(_exercises_dataset(rows, session_id))


@router.delete("/sessions/{session_id}", response_model=None)
def delete_session(session_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM workout.workout_log WHERE workout_id = %s RETURNING workout_id",
                (session_id,),
            )
            deleted = cur.fetchone()
            cur.execute("DELETE FROM workout.workout_session WHERE workout_id = %s RETURNING 1", (session_id,))
            had_session_row = cur.fetchone()
        conn.commit()

    if deleted is None and had_session_row is None:
        return api_error("NOT_FOUND", f"session {session_id} not found", status=404)

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="workout_session",
            label="Workout Sessions",
            total=0, page=1, page_size=1, row_actions=[],
        ),
        **{"schema": SESSION_SCHEMA},
        rows=[],
    ))


# ── Exercises ─────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/exercises", response_model=None)
def list_exercises(session_id: str) -> JSONResponse:
    with get_db() as conn:
        rows = _fetch_exercises(conn, session_id)

    if not rows:
        # Distinguish "session exists but empty" from "session not found"
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM workout.workout_session WHERE workout_id = %s",
                    (session_id,),
                )
                exists = cur.fetchone()
        if not exists:
            return api_error("NOT_FOUND", f"session {session_id} not found", status=404)

    return dataset_response(_exercises_dataset(rows, session_id))


@router.post("/sessions/{session_id}/exercises", response_model=None)
def add_exercise(session_id: str, body: ExerciseCreate) -> JSONResponse:
    if not body.exercise.strip():
        return api_error("VALIDATION_ERROR", "exercise cannot be empty")
    if body.status not in ("planned", "done"):
        return api_error("VALIDATION_ERROR", "status must be 'planned' or 'done'")
    if body.status == "done" and not _has_reps(body):
        return api_error("VALIDATION_ERROR", "at least one set must have reps")

    with get_db() as conn:
        with conn.cursor() as cur:
            # Session context: lifecycle row if present, else any existing exercise row (legacy)
            cur.execute(
                """
                SELECT workout_date, split FROM workout.workout_session WHERE workout_id = %s
                UNION ALL
                (SELECT workout_date, split FROM workout.workout_log WHERE workout_id = %s LIMIT 1)
                LIMIT 1
                """,
                (session_id, session_id),
            )
            session = cur.fetchone()
            if not session:
                return api_error("NOT_FOUND", f"session {session_id} not found", status=404)
            if body.status == "planned":
                cur.execute(
                    "SELECT 1 FROM workout.workout_session WHERE workout_id = %s AND status = 'active'",
                    (session_id,),
                )
                if not cur.fetchone():
                    return api_error("VALIDATION_ERROR", "planned exercises can only be added to the active session")

            cur.execute(
                """
                INSERT INTO workout.workout_log (
                    workout_id, workout_date, split, exercise, weight_kg,
                    set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    session["workout_date"],
                    session["split"],
                    body.exercise.strip(),
                    body.weight_kg,
                    body.set1_reps, body.set2_reps, body.set3_reps, body.set4_reps, body.set5_reps,
                    body.comment, body.status,
                ),
            )
        conn.commit()
        rows = _fetch_exercises(conn, session_id)

    return dataset_response(_exercises_dataset(rows, session_id))


@router.patch("/exercises/{exercise_id}", response_model=None)
def update_exercise(exercise_id: str, body: ExerciseUpdate) -> JSONResponse:
    if not body.exercise.strip():
        return api_error("VALIDATION_ERROR", "exercise cannot be empty")
    if not _has_reps(body):
        return api_error("VALIDATION_ERROR", "at least one set must have reps")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workout.workout_log SET
                    exercise   = %s,
                    weight_kg  = %s,
                    set1_reps  = %s,
                    set2_reps  = %s,
                    set3_reps  = %s,
                    set4_reps  = %s,
                    set5_reps  = %s,
                    comment    = %s,
                    status     = 'done',
                    updated_at = NOW(),
                    -- a set without reps was not performed: its timing goes with it
                    set1_started_at = CASE WHEN %s IS NULL THEN NULL ELSE set1_started_at END,
                    set1_ended_at   = CASE WHEN %s IS NULL THEN NULL ELSE set1_ended_at END,
                    set2_started_at = CASE WHEN %s IS NULL THEN NULL ELSE set2_started_at END,
                    set2_ended_at   = CASE WHEN %s IS NULL THEN NULL ELSE set2_ended_at END,
                    set3_started_at = CASE WHEN %s IS NULL THEN NULL ELSE set3_started_at END,
                    set3_ended_at   = CASE WHEN %s IS NULL THEN NULL ELSE set3_ended_at END,
                    set4_started_at = CASE WHEN %s IS NULL THEN NULL ELSE set4_started_at END,
                    set4_ended_at   = CASE WHEN %s IS NULL THEN NULL ELSE set4_ended_at END,
                    set5_started_at = CASE WHEN %s IS NULL THEN NULL ELSE set5_started_at END,
                    set5_ended_at   = CASE WHEN %s IS NULL THEN NULL ELSE set5_ended_at END
                WHERE workout_log_id = %s
                RETURNING workout_id
                """,
                (
                    body.exercise.strip(), body.weight_kg,
                    body.set1_reps, body.set2_reps, body.set3_reps, body.set4_reps, body.set5_reps,
                    body.comment,
                    *[r for r in (body.set1_reps, body.set2_reps, body.set3_reps, body.set4_reps, body.set5_reps) for _ in (0, 1)],
                    exercise_id,
                ),
            )
            updated = cur.fetchone()
        conn.commit()

    if updated is None:
        return api_error("NOT_FOUND", f"exercise {exercise_id} not found", status=404)

    with get_db() as conn:
        rows = _fetch_exercises(conn, str(updated["workout_id"]))

    return dataset_response(_exercises_dataset(rows, str(updated["workout_id"])))


# ── Set events (active workout only) ─────────────────────────────────────────
# Time authority: the SERVER clock (NOW()) stamps every set event; the client never supplies a
# time. All three endpoints are idempotent: a repeated start/confirm never moves an existing
# timestamp, so retries and double taps cannot create duplicate timing events.
# They only work on exercises of the ACTIVE session; past sessions are edited via PATCH
# /exercises/{id} and never receive timing events.
# A set is "performed" once its reps are persisted: only /confirm writes reps in this flow.

def _set_no(n: int) -> bool:
    return 1 <= n <= 5


def _active_exercise(cur: Any, exercise_id: str) -> Any:
    """Return the exercise row if it belongs to the active session, else an api_error response."""
    cur.execute(
        """
        SELECT l.workout_log_id, l.workout_id, l.status
        FROM workout.workout_log l
        JOIN workout.workout_session s ON s.workout_id = l.workout_id AND s.status = 'active'
        WHERE l.workout_log_id = %s
        FOR UPDATE OF l
        """,
        (exercise_id,),
    )
    row = cur.fetchone()
    if row:
        return row
    cur.execute("SELECT 1 FROM workout.workout_log WHERE workout_log_id = %s", (exercise_id,))
    if cur.fetchone():
        return api_error("SESSION_NOT_ACTIVE", "set timing only applies to the active workout", status=409)
    return api_error("NOT_FOUND", f"exercise {exercise_id} not found", status=404)


def _set_event_response(conn: Any, workout_id: Any) -> JSONResponse:
    return dataset_response(_exercises_dataset(_fetch_exercises(conn, str(workout_id)), str(workout_id)))


@router.post("/exercises/{exercise_id}/sets/{n}/start", response_model=None)
def start_set(exercise_id: str, n: int) -> JSONResponse:
    """The user tapped set n to begin it. Sets setN_started_at once; a no-op if the set is already
    started or already confirmed (a confirmed set keeps whatever start it had, possibly none)."""
    if not _set_no(n):
        return api_error("VALIDATION_ERROR", "set number must be 1..5")
    with get_db() as conn:
        with conn.cursor() as cur:
            ex = _active_exercise(cur, exercise_id)
            if isinstance(ex, JSONResponse):
                return ex
            cur.execute(
                f"UPDATE workout.workout_log SET set{n}_started_at = COALESCE(set{n}_started_at, NOW()) "
                f"WHERE workout_log_id = %s AND set{n}_ended_at IS NULL",
                (exercise_id,),
            )
        conn.commit()
        return _set_event_response(conn, ex["workout_id"])


@router.post("/exercises/{exercise_id}/sets/{n}/confirm", response_model=None)
def confirm_set(exercise_id: str, n: int, body: SetConfirm) -> JSONResponse:
    """The user tapped set n's checkmark. Persists the reps (and the exercise weight), marks the
    exercise 'done', and sets setN_ended_at once. Re-confirming (e.g. corrected reps) updates the
    reps but never moves the timestamps. A missing start stays NULL."""
    if not _set_no(n):
        return api_error("VALIDATION_ERROR", "set number must be 1..5")
    if body.reps < 0:
        return api_error("VALIDATION_ERROR", "reps cannot be negative")
    if body.weight_kg is not None and body.weight_kg < 0:
        return api_error("VALIDATION_ERROR", "weight cannot be negative")
    with get_db() as conn:
        with conn.cursor() as cur:
            ex = _active_exercise(cur, exercise_id)
            if isinstance(ex, JSONResponse):
                return ex
            cur.execute(
                f"""
                UPDATE workout.workout_log SET
                    set{n}_reps = %s,
                    weight_kg = %s,
                    set{n}_ended_at = COALESCE(set{n}_ended_at, NOW()),
                    status = 'done',
                    updated_at = NOW()
                WHERE workout_log_id = %s
                """,
                (body.reps, body.weight_kg, exercise_id),
            )
        conn.commit()
        return _set_event_response(conn, ex["workout_id"])


@router.post("/exercises/{exercise_id}/sets/{n}/unconfirm", response_model=None)
def unconfirm_set(exercise_id: str, n: int) -> JSONResponse:
    """Take a confirmation back: clears set n's reps AND both timestamps (the set returns to
    'not started', so a later re-confirm cannot produce an inflated duration). If no set has
    reps any more the exercise returns to 'planned'."""
    if not _set_no(n):
        return api_error("VALIDATION_ERROR", "set number must be 1..5")
    with get_db() as conn:
        with conn.cursor() as cur:
            ex = _active_exercise(cur, exercise_id)
            if isinstance(ex, JSONResponse):
                return ex
            others_empty = " AND ".join(f"set{i}_reps IS NULL" for i in range(1, 6) if i != n)
            cur.execute(
                f"""
                UPDATE workout.workout_log SET
                    set{n}_reps = NULL, set{n}_started_at = NULL, set{n}_ended_at = NULL,
                    status = CASE WHEN {others_empty} THEN 'planned' ELSE status END,
                    updated_at = NOW()
                WHERE workout_log_id = %s
                """,
                (exercise_id,),
            )
        conn.commit()
        return _set_event_response(conn, ex["workout_id"])


@router.patch("/exercises/{exercise_id}/details", response_model=None)
def update_exercise_details(exercise_id: str, body: ExerciseDetails) -> JSONResponse:
    """Name, weight and comment of an exercise in the active workout, without touching sets,
    status or timing. Partial-update semantics: all three fields are always sent; an explicit
    null weight_kg / comment clears the value."""
    if not body.exercise.strip():
        return api_error("VALIDATION_ERROR", "exercise cannot be empty")
    if body.weight_kg is not None and body.weight_kg < 0:
        return api_error("VALIDATION_ERROR", "weight cannot be negative")
    with get_db() as conn:
        with conn.cursor() as cur:
            ex = _active_exercise(cur, exercise_id)
            if isinstance(ex, JSONResponse):
                return ex
            cur.execute(
                "UPDATE workout.workout_log SET exercise = %s, weight_kg = %s, comment = %s, "
                "updated_at = NOW() WHERE workout_log_id = %s",
                (body.exercise.strip(), body.weight_kg, body.comment if body.comment and body.comment.strip() else None, exercise_id),
            )
        conn.commit()
        return _set_event_response(conn, ex["workout_id"])


HISTORY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",          label="ID",          type="string", sortable=False, detail_visible=False),
    ColumnSchema(key="workout_date", label="Date",        type="date",   sortable=True),
    ColumnSchema(key="set1_reps",   label="Set 1 (reps)", type="number", sortable=False),
    ColumnSchema(key="set2_reps",   label="Set 2 (reps)", type="number", sortable=False),
    ColumnSchema(key="set3_reps",   label="Set 3 (reps)", type="number", sortable=False),
    ColumnSchema(key="set4_reps",   label="Set 4 (reps)", type="number", sortable=False),
    ColumnSchema(key="set5_reps",   label="Set 5 (reps)", type="number", sortable=False),
    ColumnSchema(key="weight_kg",   label="Weight (kg)",  type="number", sortable=True,  format="kg"),
    ColumnSchema(key="comment",     label="Comment",      type="string", sortable=False),
    ColumnSchema(key="split",       label="Split",        type="string", sortable=False),
]


@router.get("/exercises/history", response_model=None)
def exercise_history(name: str) -> JSONResponse:
    """Performed occurrences of an exercise (case-insensitive name, any archetype), oldest first.

    Ordering: workout_date, created_at, id. Empty result: an empty dataset. Timing columns
    (started_at, ended_at, duration_sec, rest_avg_sec, time_of_day) come from the measured-only
    view workout.exercise_timing and are null when not measured; time_of_day is local to the
    workout's stored time zone (Europe/Berlin for legacy sessions).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    l.workout_log_id::text AS id,
                    l.workout_id::text     AS session_id,
                    l.workout_date::text   AS workout_date,
                    l.set1_reps, l.set2_reps, l.set3_reps, l.set4_reps, l.set5_reps,
                    l.weight_kg, l.comment, l.split,
                    t.started_at, t.ended_at, t.duration_sec, t.rest_avg_sec, t.time_of_day
                FROM workout.workout_log l
                LEFT JOIN workout.exercise_timing t USING (workout_log_id)
                WHERE LOWER(l.exercise) = LOWER(%s) AND l.status = 'done'
                ORDER BY l.workout_date ASC, l.created_at ASC, l.workout_log_id ASC
                """,
                (name,),
            )
            rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        if r.get("weight_kg") is not None:
            r["weight_kg"] = float(r["weight_kg"])
        for k in ("started_at", "ended_at"):
            if r.get(k) is not None:
                r[k] = r[k].isoformat()

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="exercise_history",
            label=f"History — {name}",
            total=len(rows),
            page=1,
            page_size=len(rows) or 1,
        ),
        schema_=HISTORY_SCHEMA,
        rows=rows,
    ))


NAME_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="exercise",  label="Exercise", type="string", sortable=False),
    ColumnSchema(key="use_count", label="Uses",     type="number", sortable=False),
]


@router.get("/exercises/names", response_model=None)
def exercise_names() -> JSONResponse:
    """Distinct performed exercise names across all archetypes (case-insensitive),
    most-used first; display name = most recent spelling. Feeds Add Exercise suggestions."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT (ARRAY_AGG(exercise ORDER BY workout_date DESC, created_at DESC))[1] AS exercise,
                       COUNT(*)::int AS use_count
                FROM workout.workout_log
                WHERE status = 'done'
                GROUP BY LOWER(TRIM(exercise))
                ORDER BY COUNT(*) DESC, 1 ASC
                """
            )
            rows = [{"id": r["exercise"], **dict(r)} for r in cur.fetchall()]

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="workout_exercise_name",
            label="Exercise names",
            total=len(rows),
            page=1,
            page_size=len(rows) or 1,
        ),
        **{"schema": NAME_SCHEMA},
        rows=rows,
    ))


@router.get("/sessions/{session_id}/progress", response_model=None)
def session_exercise_progress(session_id: str) -> JSONResponse:
    """Per-exercise progress for a session, read from the exercise_session_history view."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT exercise, total_reps, delta
                FROM workout.exercise_session_history
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_id,),
            )
            rows = cur.fetchall()

    progress_schema: list[ColumnSchema] = [
        ColumnSchema(key="exercise",   label="Exercise",    type="string", sortable=False),
        ColumnSchema(key="total_reps", label="Total Reps",  type="number", sortable=False),
        ColumnSchema(key="delta",      label="vs Last Time",type="number", sortable=False),
    ]

    return dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="exercise_progress",
            label="Session Progress",
            total=len(rows),
            page=1,
            page_size=len(rows) or 1,
        ),
        **{"schema": progress_schema},
        rows=[
            {
                "id": str(i),
                "exercise": r["exercise"],
                "total_reps": int(r["total_reps"]),
                "delta": int(r["delta"]) if r["delta"] is not None else None,
            }
            for i, r in enumerate(rows)
        ],
    ))


@router.delete("/exercises/{exercise_id}", response_model=None)
def delete_exercise(exercise_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM workout.workout_log WHERE workout_log_id = %s RETURNING workout_id",
                (exercise_id,),
            )
            deleted = cur.fetchone()
        conn.commit()

    if deleted is None:
        return api_error("NOT_FOUND", f"exercise {exercise_id} not found", status=404)

    with get_db() as conn:
        rows = _fetch_exercises(conn, str(deleted["workout_id"]))

    return dataset_response(_exercises_dataset(rows, str(deleted["workout_id"])))


# ── Client freeze diagnostics ─────────────────────────────────────────────────

class ClientPerfEvent(BaseModel):
    """One browser-side stall report. Diagnostic only; nothing is stored beyond the log line."""
    kind: str = Field(max_length=16)        # longtask | gap | slow_fetch
    ms: int = Field(ge=0, le=3_600_000)
    path: str = Field(max_length=200)
    last_action: str = Field(default="", max_length=120)
    detail: str = Field(default="", max_length=200)


@router.post("/client-perf", response_model=None, status_code=204)
def client_perf(events: list[ClientPerfEvent] = Body(max_length=20)) -> Response:
    for e in events:
        perf_log.warning("CLIENT_STALL kind=%s ms=%d path=%s last_action=%r detail=%r",
                         e.kind, e.ms, e.path, e.last_action, e.detail)
    return Response(status_code=204)
