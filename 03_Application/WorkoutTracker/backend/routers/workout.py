import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/workout", tags=["workout"])

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


class ExerciseCreate(BaseModel):
    exercise:  str
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
            SELECT workout_log_id, exercise, weight_kg,
                   set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment
            FROM workout.workout_log
            WHERE workout_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        return cur.fetchall()


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=None)
def list_sessions(page: int = 1, page_size: int = 25) -> JSONResponse:
    if page < 1:
        return api_error("INVALID_PARAM", "page must be ≥ 1")

    offset = (page - 1) * page_size

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT workout_id) FROM workout.workout_log")
            total = int(cur.fetchone()["count"])
            cur.execute(
                """
                SELECT
                    workout_id::text        AS id,
                    MAX(workout_date)::text AS workout_date,
                    MAX(split)              AS split,
                    COUNT(*)::int           AS exercise_count
                FROM workout.workout_log
                GROUP BY workout_id
                ORDER BY MAX(workout_date) DESC, MAX(created_at) DESC
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = [dict(r) for r in cur.fetchall()]

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
        conn.commit()

    if deleted is None:
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
                    "SELECT 1 FROM workout.workout_log WHERE workout_id = %s LIMIT 1",
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
    if not _has_reps(body):
        return api_error("VALIDATION_ERROR", "at least one set must have reps")

    with get_db() as conn:
        with conn.cursor() as cur:
            # Derive workout_date and split from the existing session
            cur.execute(
                """
                SELECT workout_date, split
                FROM workout.workout_log
                WHERE workout_id = %s
                LIMIT 1
                """,
                (session_id,),
            )
            session = cur.fetchone()
            if not session:
                return api_error("NOT_FOUND", f"session {session_id} not found", status=404)

            cur.execute(
                """
                INSERT INTO workout.workout_log (
                    workout_id, workout_date, split, exercise, weight_kg,
                    set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    session["workout_date"],
                    session["split"],
                    body.exercise.strip(),
                    body.weight_kg,
                    body.set1_reps, body.set2_reps, body.set3_reps, body.set4_reps, body.set5_reps,
                    body.comment,
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
                    updated_at = NOW()
                WHERE workout_log_id = %s
                RETURNING workout_id
                """,
                (
                    body.exercise.strip(), body.weight_kg,
                    body.set1_reps, body.set2_reps, body.set3_reps, body.set4_reps, body.set5_reps,
                    body.comment,
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


HISTORY_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",          label="ID",          type="string", sortable=False, detail_visible=False),
    ColumnSchema(key="workout_date", label="Date",        type="date",   sortable=True),
    ColumnSchema(key="set1_reps",   label="Set 1 (reps)", type="number", sortable=False),
    ColumnSchema(key="set2_reps",   label="Set 2 (reps)", type="number", sortable=False),
    ColumnSchema(key="set3_reps",   label="Set 3 (reps)", type="number", sortable=False),
    ColumnSchema(key="set4_reps",   label="Set 4 (reps)", type="number", sortable=False),
    ColumnSchema(key="set5_reps",   label="Set 5 (reps)", type="number", sortable=False),
    ColumnSchema(key="weight_kg",   label="Weight (kg)",  type="number", sortable=True,  format="kg"),
]


@router.get("/exercises/history", response_model=None)
def exercise_history(name: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    workout_log_id::text AS id,
                    workout_date::text   AS workout_date,
                    set1_reps, set2_reps, set3_reps, set4_reps, set5_reps,
                    weight_kg
                FROM workout.workout_log
                WHERE LOWER(exercise) = LOWER(%s)
                ORDER BY workout_date ASC, created_at ASC
                """,
                (name,),
            )
            rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        if r.get("weight_kg") is not None:
            r["weight_kg"] = float(r["weight_kg"])

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
