"""
Sprint 04 — Standards management endpoints.

Endpoints:
  PATCH  /api/food/entries/{id}/standard         → toggle_standard
  GET    /api/food/standards                      → get_standards_page
  POST   /api/food/standards/{standard_id}/log   → log_from_standard
  DELETE /api/food/standards/{standard_id}/today-instance → delete_today_instance

Invariants enforced here:
- POST log always sets standard = FALSE on the new row (no override).
- POST log always sets source_standard_id = standard_id.
- DELETE today-instance uses a two-step SELECT-then-DELETE approach.
- No imports from food.py, entries.py, or report.py.
"""

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse, Response

from backend.database import get_db

router = APIRouter(prefix="/food", tags=["food-standards"])


# ── Private helpers ────────────────────────────────────────────────────────────

def _api_err(code: str, message: str, detail: Any, status: int) -> JSONResponse:
    """Build a JSONResponse wrapping an ApiError envelope."""
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "detail": detail,
                "request_id": uuid.uuid4().hex[:8],
            }
        },
    )


def _dt_str(val: Any) -> str:
    """Serialise a datetime or timestamp value to 'YYYY-MM-DDTHH:MM:SS'."""
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%dT%H:%M:%S")
    return str(val)


def _serialise_standard_log_result(row: dict) -> dict:
    """
    Convert a psycopg2 RealDictRow from the log_from_standard INSERT RETURNING
    into a Sprint 04 v1.1 EntryDetail dict.

    Serialisation rules:
    - id as str
    - logged_at / created_at / updated_at as 'YYYY-MM-DDTHH:MM:SS' (naive)
    - kcal and confidence as int
    - all other numerics as float
    - notes as str or None
    - standard as bool
    - source_standard_id as str or None
    - alcohol_g is NOT included in the output (excluded from API in this slice)
    """
    return {
        "id":                 str(row["id"]),
        "logged_at":          _dt_str(row["logged_at"]),
        "meal_type":          row["meal_type"],
        "dish_name":          row["dish_name"],
        "kcal":               int(row["kcal"]),
        "protein_g":          float(row["protein_g"]),
        "carbs_g":            float(row["carbs_g"]),
        "fat_g":              float(row["fat_g"]),
        "fiber_g":            float(row["fiber_g"]),
        "good_fat_g":         float(row["good_fat_g"]),
        "meat_g":             float(row["meat_g"]),
        "red_meat_g":         float(row["red_meat_g"]),
        "sodium_mg":          float(row["sodium_mg"]),
        "confidence":         int(row["confidence"]),
        "notes":              row["notes"],
        "created_at":         _dt_str(row["created_at"]),
        "updated_at":         _dt_str(row["updated_at"]),
        "standard":           bool(row["standard"]),
        "source_standard_id": str(row["source_standard_id"]) if row["source_standard_id"] else None,
    }


def _serialise_standard_dish(row: dict) -> dict:
    """
    Convert a foodtracker.food_logs row (from the standards query) into a
    StandardDish dict per the StandardsPagePayload contract.
    """
    return {
        "id":          str(row["id"]),
        "meal_type":   row["meal_type"],
        "dish_name":   row["dish_name"],
        "kcal":        int(row["kcal"]),
        "protein_g":   float(row["protein_g"]),
        "carbs_g":     float(row["carbs_g"]),
        "fat_g":       float(row["fat_g"]),
        "fiber_g":     float(row["fiber_g"]),
        "good_fat_g":  float(row["good_fat_g"]),
        "meat_g":      float(row["meat_g"]),
        "red_meat_g":  float(row["red_meat_g"]),
        "sodium_mg":   float(row["sodium_mg"]),
        "confidence":  int(row["confidence"]),
    }


def _serialise_today_instance(row: dict) -> dict:
    """
    Convert a GROUP BY aggregate row (from the today_instances query) into a
    TodayInstance dict per the StandardsPagePayload contract.
    """
    return {
        "source_standard_id": str(row["source_standard_id"]),
        "dish_name":          row["dish_name"],
        "meal_type":          row["meal_type"],
        "count":              int(row["count"]),
        "total_kcal":         int(row["total_kcal"]),
        "total_protein_g":    float(row["total_protein_g"]),
        "total_carbs_g":      float(row["total_carbs_g"]),
        "total_fat_g":        float(row["total_fat_g"]),
        "total_fiber_g":      float(row["total_fiber_g"]),
        "total_good_fat_g":   float(row["total_good_fat_g"]),
        "total_meat_g":       float(row["total_meat_g"]),
        "total_red_meat_g":   float(row["total_red_meat_g"]),
        "total_sodium_mg":    float(row["total_sodium_mg"]),
    }


# ── Route handlers ─────────────────────────────────────────────────────────────

@router.patch("/entries/{entry_id}/standard", response_model=None)
async def toggle_standard(entry_id: str, request: Request) -> JSONResponse:
    """
    PATCH /api/food/entries/{id}/standard

    Body: { "desired_standard": true | false }

    Parses JSON body. Returns HTTP 422 if body is invalid or desired_standard
    is absent or not a boolean. Checks entry existence; returns HTTP 404 if
    not found. Updates the standard column and returns StandardToggleResult.
    """
    try:
        body = await request.body()
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return _api_err(
            "VALIDATION_ERROR",
            "Request body is not valid JSON",
            {"field": "body", "reason": "PARSE_ERROR"},
            422,
        )

    if not isinstance(data, dict) or "desired_standard" not in data:
        return _api_err(
            "VALIDATION_ERROR",
            "desired_standard is required",
            {"field": "desired_standard", "reason": "MISSING_FIELD"},
            422,
        )

    desired_standard = data["desired_standard"]
    if not isinstance(desired_standard, bool):
        return _api_err(
            "VALIDATION_ERROR",
            "desired_standard must be a boolean",
            {"field": "desired_standard", "reason": "INVALID_TYPE: expected boolean"},
            422,
        )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM foodtracker.food_logs WHERE id = %s",
                (entry_id,),
            )
            if cur.fetchone() is None:
                return _api_err(
                    "NOT_FOUND",
                    f"Entry '{entry_id}' not found",
                    {"id": entry_id},
                    404,
                )

            cur.execute(
                """
                UPDATE foodtracker.food_logs
                SET standard = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (desired_standard, entry_id),
            )
        conn.commit()

    return JSONResponse(
        status_code=200,
        content={"id": entry_id, "standard": desired_standard},
    )


@router.get("/day", response_model=None)
def get_day_page() -> JSONResponse:
    """
    GET /api/food/day

    Returns DayPagePayload: two collections —
      today_entries: ALL rows logged today (logged_at::date = CURRENT_DATE),
                     ordered by logged_at DESC
      standards:     all rows where standard=TRUE, ordered by meal_type, dish_name
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            # Query 1: all entries logged today
            cur.execute(
                """
                SELECT *
                FROM foodtracker.food_logs
                WHERE logged_at::date = CURRENT_DATE
                ORDER BY logged_at DESC
                """
            )
            today_entries = [_serialise_standard_log_result(dict(r)) for r in cur.fetchall()]

            # Query 2: all standard dishes
            cur.execute(
                """
                SELECT id, meal_type, dish_name, kcal,
                       protein_g, carbs_g, fat_g, fiber_g,
                       good_fat_g, meat_g, red_meat_g, sodium_mg, confidence
                FROM foodtracker.food_logs
                WHERE standard = TRUE
                ORDER BY meal_type, dish_name
                """
            )
            standards = [_serialise_standard_dish(dict(r)) for r in cur.fetchall()]

    return JSONResponse(
        status_code=200,
        content={"today_entries": today_entries, "standards": standards},
    )


@router.get("/standards", response_model=None)
def get_standards_page() -> JSONResponse:
    """
    GET /api/food/standards

    Returns StandardsPagePayload: two collections —
      standards:      all rows where standard=TRUE, ordered by meal_type, dish_name
      today_instances: aggregated rows for today where source_standard_id IS NOT NULL,
                       grouped by source_standard_id/dish_name/meal_type,
                       ordered by MAX(logged_at) DESC
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            # Query 1: all standard dishes
            cur.execute(
                """
                SELECT id, meal_type, dish_name, kcal,
                       protein_g, carbs_g, fat_g, fiber_g,
                       good_fat_g, meat_g, red_meat_g, sodium_mg, confidence
                FROM foodtracker.food_logs
                WHERE standard = TRUE
                ORDER BY meal_type, dish_name
                """
            )
            standards = [_serialise_standard_dish(dict(r)) for r in cur.fetchall()]

            # Query 2: today's aggregated standard-derived rows
            cur.execute(
                """
                SELECT
                    source_standard_id,
                    dish_name,
                    meal_type,
                    COUNT(*)          AS count,
                    SUM(kcal)         AS total_kcal,
                    SUM(protein_g)    AS total_protein_g,
                    SUM(carbs_g)      AS total_carbs_g,
                    SUM(fat_g)        AS total_fat_g,
                    SUM(fiber_g)      AS total_fiber_g,
                    SUM(good_fat_g)   AS total_good_fat_g,
                    SUM(meat_g)       AS total_meat_g,
                    SUM(red_meat_g)   AS total_red_meat_g,
                    SUM(sodium_mg)    AS total_sodium_mg
                FROM foodtracker.food_logs
                WHERE source_standard_id IS NOT NULL
                  AND logged_at::date = CURRENT_DATE
                GROUP BY source_standard_id, dish_name, meal_type
                ORDER BY MAX(logged_at) DESC
                """
            )
            today_instances = [_serialise_today_instance(dict(r)) for r in cur.fetchall()]

    return JSONResponse(
        status_code=200,
        content={"standards": standards, "today_instances": today_instances},
    )


@router.post("/standards/{standard_id}/log", response_model=None)
def log_from_standard(standard_id: str) -> JSONResponse:
    """
    POST /api/food/standards/{standard_id}/log

    Fetches the standard row, validates it is marked standard=TRUE, then inserts
    a new row copying all nutrition values. The new row always has:
      standard = FALSE  (firm invariant — copies are never standards)
      source_standard_id = standard_id
      logged_at = datetime.now()

    Returns the inserted row as EntryDetail (Sprint 04 v1.1) with HTTP 201.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM foodtracker.food_logs WHERE id = %s",
                (standard_id,),
            )
            source = cur.fetchone()

        if source is None:
            return _api_err(
                "NOT_FOUND",
                f"Standard '{standard_id}' not found",
                {"id": standard_id},
                404,
            )

        source = dict(source)

        if not source["standard"]:
            return _api_err(
                "NOT_A_STANDARD",
                f"Entry '{standard_id}' is not marked as a standard",
                {"id": standard_id},
                422,
            )

        new_id = str(uuid.uuid4())
        new_logged_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO foodtracker.food_logs (
                    id, logged_at, meal_type, dish_name,
                    kcal, protein_g, carbs_g, fat_g, fiber_g, good_fat_g,
                    meat_g, red_meat_g, sodium_mg, confidence, notes,
                    standard, source_standard_id, alcohol_g
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    FALSE, %s, %s
                ) RETURNING *
                """,
                (
                    new_id,
                    new_logged_at,
                    source["meal_type"],
                    source["dish_name"],
                    source["kcal"],
                    source["protein_g"],
                    source["carbs_g"],
                    source["fat_g"],
                    source["fiber_g"],
                    source["good_fat_g"],
                    source["meat_g"],
                    source["red_meat_g"],
                    source["sodium_mg"],
                    source["confidence"],
                    source["notes"],
                    standard_id,          # source_standard_id
                    source["alcohol_g"],  # copy alcohol_g from source
                ),
            )
            inserted = dict(cur.fetchone())
        conn.commit()

    return JSONResponse(
        status_code=201,
        content=_serialise_standard_log_result(inserted),
    )


@router.delete("/standards/{standard_id}/today-instance", response_model=None)
def delete_today_instance(standard_id: str) -> Response:
    """
    DELETE /api/food/standards/{standard_id}/today-instance

    Two-step approach (SELECT then DELETE by id):
    1. SELECT id ... WHERE source_standard_id = %s AND logged_at::date = CURRENT_DATE
       ORDER BY logged_at DESC LIMIT 1
    2. If no row: return HTTP 404 (NO_TODAY_INSTANCE)
    3. DELETE FROM foodtracker.food_logs WHERE id = <that id>
    4. Return HTTP 204

    The two-step approach avoids ambiguity and ensures the most-recent row is
    targeted. DELETE ... WHERE ... LIMIT 1 is not standard SQL.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM foodtracker.food_logs
                WHERE source_standard_id = %s
                  AND logged_at::date = CURRENT_DATE
                ORDER BY logged_at DESC
                LIMIT 1
                """,
                (standard_id,),
            )
            row = cur.fetchone()

        if row is None:
            return _api_err(
                "NO_TODAY_INSTANCE",
                f"No logged instance found today for standard '{standard_id}'",
                {"standard_id": standard_id},
                404,
            )

        target_id = row["id"]

        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM foodtracker.food_logs WHERE id = %s",
                (target_id,),
            )
        conn.commit()

    return Response(status_code=204)
