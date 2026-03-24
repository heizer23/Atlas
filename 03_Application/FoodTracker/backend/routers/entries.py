import json
import uuid
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.errors
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.database import get_db
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/food", tags=["food-entries"])

# ── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack", "other"}

# Column order per architecture.json deferrals.application_implementer:
# id (string, sortable=False, detail_visible=False),
# logged_at (date, sortable=True),
# meal_type (string, sortable=True, filterable=True),
# dish_name (string, sortable=True),
# kcal (number, format='kcal', sortable=True).
# protein_g and fat_g added as detail_visible for richer display.

ENTRIES_OVERVIEW_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",         label="ID",          type="string", sortable=False, detail_visible=False),
    ColumnSchema(key="logged_at",  label="Date / Time", type="date",   sortable=True),
    ColumnSchema(key="meal_type",  label="Meal",         type="string", sortable=True,  filterable=True),
    ColumnSchema(key="dish_name",  label="Dish",         type="string", sortable=True),
    ColumnSchema(key="kcal",       label="kcal",         type="number", sortable=True,  format="kcal"),
    ColumnSchema(key="protein_g",  label="Protein (g)",  type="number", sortable=True,  format="g",  detail_visible=True),
    ColumnSchema(key="fat_g",      label="Fat (g)",      type="number", sortable=True,  format="g",  detail_visible=True),
    # Sprint 04: standard flag — used by frontend to render correct three-dots menu label
    ColumnSchema(key="standard",   label="Standard",     type="boolean", sortable=False, detail_visible=False),
]

# ── Private helpers ────────────────────────────────────────────────────────────

def _err(code: str, message: str, field: str, reason: str) -> dict:
    """Build an ApiError-shaped dict. Route handler turns this into a JSONResponse."""
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": {"field": field, "reason": reason},
            "request_id": uuid.uuid4().hex[:8],
        }
    }


def _serialise_entry_detail(row: dict) -> dict:
    """
    Convert a psycopg2 RealDictRow (from SELECT *) into an EntryDetail dict
    conforming to architecture.json contracts.named_contracts.EntryDetail.

    Serialisation rules:
    - id serialised as str (UUID hex with hyphens)
    - logged_at, created_at, updated_at serialised as 'YYYY-MM-DDTHH:MM:SS'
      (naive, no timezone suffix) — psycopg2 returns TIMESTAMP WITHOUT TIME ZONE
      columns as naive datetime objects; use strftime to guarantee the format.
    - kcal and confidence serialised as int
    - All other numeric fields serialised as float
    - notes is None when not stored
    """

    def _dt_str(val: Any) -> str:
        if hasattr(val, "strftime"):
            return val.strftime("%Y-%m-%dT%H:%M:%S")
        return str(val)

    return {
        "id":         str(row["id"]),
        "logged_at":  _dt_str(row["logged_at"]),
        "meal_type":  row["meal_type"],
        "dish_name":  row["dish_name"],
        "kcal":       int(row["kcal"]),
        "protein_g":  float(row["protein_g"]),
        "carbs_g":    float(row["carbs_g"]),
        "fat_g":      float(row["fat_g"]),
        "fiber_g":    float(row["fiber_g"]),
        "good_fat_g": float(row["good_fat_g"]),
        "meat_g":     float(row["meat_g"]),
        "red_meat_g": float(row["red_meat_g"]),
        "sodium_mg":  float(row["sodium_mg"]),
        "confidence":         int(row["confidence"]),
        "notes":              row["notes"],
        "created_at":         _dt_str(row["created_at"]),
        "updated_at":         _dt_str(row["updated_at"]),
        # Sprint 04 v1.1 extension
        "standard":           bool(row["standard"]),
        "source_standard_id": str(row["source_standard_id"]) if row["source_standard_id"] else None,
    }


def _validate_entry_edit_request(body: bytes) -> tuple[dict, None] | tuple[None, dict]:
    """
    Parse and validate the PUT /api/food/entries/{id} request body against
    the EntryEditRequest contract (architecture.json contracts.named_contracts.EntryEditRequest).

    Returns (validated_dict, None) on success.
    Returns (None, error_dict) on failure — error_dict is ApiError-shaped.

    Validation order:
    1. JSON parse — must be a JSON object
    2. logged_at — required, parseable datetime string
    3. meal_type — required, must be in allowed enum
    4. dish_name — required, non-empty string
    5. kcal — required, non-negative integer
    6. protein_g, carbs_g, fat_g — required, non-negative floats
    7. fiber_g, good_fat_g, meat_g, red_meat_g, sodium_mg — optional, non-negative floats
    8. confidence — optional integer 1–5 (default 3)
    9. notes — optional string

    Does NOT call or reference _validate_and_normalise.
    Edit and intake are separate flows (Option A, product decision 2026-03-21).
    """

    # Step 1 — JSON parse
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None, _err(
            "VALIDATION_ERROR",
            "Request body is not valid JSON",
            "body",
            "PARSE_ERROR: body could not be decoded as JSON",
        )

    if not isinstance(data, dict):
        return None, _err(
            "VALIDATION_ERROR",
            "Request body must be a JSON object",
            "body",
            "PARSE_ERROR: expected object at root",
        )

    # Step 2 — logged_at
    raw_logged_at = data.get("logged_at")
    if raw_logged_at is None:
        return None, _err(
            "VALIDATION_ERROR",
            "logged_at is required",
            "logged_at",
            "MISSING_FIELD: field is absent",
        )
    try:
        parsed_logged_at = datetime.fromisoformat(str(raw_logged_at))
    except ValueError:
        return None, _err(
            "VALIDATION_ERROR",
            f"logged_at '{raw_logged_at}' is not a valid datetime string",
            "logged_at",
            "INVALID_FIELD: must be ISO-8601 datetime e.g. '2026-03-20T12:30:00'",
        )
    logged_at = parsed_logged_at.strftime("%Y-%m-%dT%H:%M:%S")

    # Step 3 — meal_type
    raw_meal_type = data.get("meal_type")
    if raw_meal_type is None:
        return None, _err(
            "VALIDATION_ERROR",
            "meal_type is required",
            "meal_type",
            "MISSING_FIELD: field is absent",
        )
    meal_type = str(raw_meal_type).strip()
    if meal_type not in ALLOWED_MEAL_TYPES:
        return None, _err(
            "VALIDATION_ERROR",
            f"meal_type '{meal_type}' is not allowed",
            "meal_type",
            f"INVALID_FIELD: must be one of {sorted(ALLOWED_MEAL_TYPES)}",
        )

    # Step 4 — dish_name
    raw_dish_name = data.get("dish_name")
    if raw_dish_name is None:
        return None, _err(
            "VALIDATION_ERROR",
            "dish_name is required",
            "dish_name",
            "MISSING_FIELD: field is absent",
        )
    dish_name = str(raw_dish_name).strip()
    if not dish_name:
        return None, _err(
            "VALIDATION_ERROR",
            "dish_name must be a non-empty string",
            "dish_name",
            "INVALID_FIELD: dish_name is empty",
        )

    # Step 5 — kcal (required, non-negative integer)
    raw_kcal = data.get("kcal")
    if raw_kcal is None:
        return None, _err(
            "VALIDATION_ERROR",
            "kcal is required",
            "kcal",
            "MISSING_FIELD: field is absent",
        )
    if not isinstance(raw_kcal, (int, float)) or isinstance(raw_kcal, bool) or raw_kcal < 0:
        return None, _err(
            "VALIDATION_ERROR",
            "kcal must be a non-negative number",
            "kcal",
            "INVALID_FIELD: must be a non-negative number",
        )
    kcal = int(round(raw_kcal))

    # Step 6 — required numeric fields
    for field_name in ("protein_g", "carbs_g", "fat_g"):
        val = data.get(field_name)
        if val is None:
            return None, _err(
                "VALIDATION_ERROR",
                f"{field_name} is required",
                field_name,
                "MISSING_FIELD: field is absent",
            )
        if not isinstance(val, (int, float)) or isinstance(val, bool) or val < 0:
            return None, _err(
                "VALIDATION_ERROR",
                f"{field_name} must be a non-negative number",
                field_name,
                "INVALID_FIELD: must be a non-negative number",
            )

    protein_g = float(data["protein_g"])
    carbs_g   = float(data["carbs_g"])
    fat_g     = float(data["fat_g"])

    # Step 7 — optional numeric fields
    def _check_optional_nonneg(key: str) -> tuple[float, dict | None]:
        raw = data.get(key)
        if raw is None:
            return 0.0, None
        if not isinstance(raw, (int, float)) or isinstance(raw, bool) or raw < 0:
            return 0.0, _err(
                "VALIDATION_ERROR",
                f"{key} must be a non-negative number",
                key,
                "INVALID_FIELD: must be a non-negative number when present",
            )
        return float(raw), None

    fiber_g,    err = _check_optional_nonneg("fiber_g");
    if err: return None, err
    good_fat_g, err = _check_optional_nonneg("good_fat_g");
    if err: return None, err
    meat_g,     err = _check_optional_nonneg("meat_g");
    if err: return None, err
    red_meat_g, err = _check_optional_nonneg("red_meat_g");
    if err: return None, err
    sodium_mg,  err = _check_optional_nonneg("sodium_mg");
    if err: return None, err

    # Step 8 — confidence (optional, integer 1–5, default 3)
    raw_conf = data.get("confidence")
    if raw_conf is not None:
        if not isinstance(raw_conf, int) or isinstance(raw_conf, bool) or not (1 <= raw_conf <= 5):
            return None, _err(
                "VALIDATION_ERROR",
                "confidence must be an integer between 1 and 5",
                "confidence",
                "INVALID_FIELD: must be integer in range [1, 5]",
            )
        confidence = raw_conf
    else:
        confidence = 3

    # Step 9 — notes (optional string)
    raw_notes = data.get("notes")
    notes = str(raw_notes) if raw_notes is not None else None

    validated: dict[str, Any] = {
        "logged_at":  logged_at,
        "meal_type":  meal_type,
        "dish_name":  dish_name,
        "kcal":       kcal,
        "protein_g":  protein_g,
        "carbs_g":    carbs_g,
        "fat_g":      fat_g,
        "fiber_g":    fiber_g,
        "good_fat_g": good_fat_g,
        "meat_g":     meat_g,
        "red_meat_g": red_meat_g,
        "sodium_mg":  sodium_mg,
        "confidence": confidence,
        "notes":      notes,
    }

    return validated, None


def _serialise_overview_row(row: dict) -> dict[str, Any]:
    """
    Serialise a foodtracker.food_logs row into a Dataset row dict using
    ENTRIES_OVERVIEW_SCHEMA field keys. Includes all ENTRIES_OVERVIEW_SCHEMA
    columns plus any additional detail_visible fields.
    """

    def _dt_str(val: Any) -> str:
        if hasattr(val, "strftime"):
            return val.strftime("%Y-%m-%dT%H:%M:%S")
        return str(val)

    return {
        "id":        str(row["id"]),
        "logged_at": _dt_str(row["logged_at"]),
        "meal_type": row["meal_type"],
        "dish_name": row["dish_name"],
        "kcal":      int(row["kcal"]),
        "protein_g": float(row["protein_g"]),
        "fat_g":     float(row["fat_g"]),
        # Sprint 04: standard flag for three-dots menu label selection
        "standard":  bool(row["standard"]),
    }


# ── Route handlers ─────────────────────────────────────────────────────────────

@router.get("/entries", response_model=None)
def list_entries() -> JSONResponse:
    """
    GET /api/food/entries — returns all rows from foodtracker.food_logs as a
    Dataset conforming to the UI data contract (ENTRIES_OVERVIEW_SCHEMA).
    Rows ordered by logged_at descending.
    row_actions: ['delete', 'copy', 'detail'].
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                # Sprint 04: include standard column so the frontend can render
                # the correct three-dots menu label per row.
                "SELECT id, logged_at, meal_type, dish_name, kcal, protein_g, fat_g, standard "
                "FROM foodtracker.food_logs ORDER BY logged_at DESC"
            )
            rows = [dict(r) for r in cur.fetchall()]

    serialised_rows = [_serialise_overview_row(r) for r in rows]

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="food_entry",
            label="Meal Entries",
            total=len(serialised_rows),
            page=1,
            page_size=len(serialised_rows),
            row_actions=["delete", "copy"],
        ),
        **{"schema": ENTRIES_OVERVIEW_SCHEMA},
        rows=serialised_rows,
    )

    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


@router.get("/entries/{entry_id}", response_model=None)
def get_entry(entry_id: str) -> JSONResponse:
    """
    GET /api/food/entries/{id} — returns the EntryDetail dict for a single row.
    Returns ApiError HTTP 404 if the row does not exist.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM foodtracker.food_logs WHERE id = %s",
                (entry_id,),
            )
            row = cur.fetchone()

    if row is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Entry '{entry_id}' not found",
                    "detail": {"id": entry_id},
                    "request_id": uuid.uuid4().hex[:8],
                }
            },
        )

    return JSONResponse(content=_serialise_entry_detail(dict(row)))


@router.put("/entries/{entry_id}", response_model=None)
async def update_entry(entry_id: str, request: Request) -> JSONResponse:
    """
    PUT /api/food/entries/{id} — validates EntryEditRequest body, updates the
    existing row in-place. Returns the updated row as a single-row Dataset.
    Returns ApiError HTTP 404 if not found, HTTP 422 on validation failure,
    HTTP 400 on DB_CONSTRAINT.

    Does NOT call _validate_and_normalise — edit and intake are separate flows
    (Option A, product decision 2026-03-21).
    """
    body = await request.body()
    validated, err = _validate_entry_edit_request(body)
    if err is not None:
        return JSONResponse(status_code=422, content=err)

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Check existence before update
                cur.execute(
                    "SELECT id FROM foodtracker.food_logs WHERE id = %s",
                    (entry_id,),
                )
                if cur.fetchone() is None:
                    return JSONResponse(
                        status_code=404,
                        content={
                            "error": {
                                "code": "NOT_FOUND",
                                "message": f"Entry '{entry_id}' not found",
                                "detail": {"id": entry_id},
                                "request_id": uuid.uuid4().hex[:8],
                            }
                        },
                    )

                cur.execute(
                    """
                    UPDATE foodtracker.food_logs
                    SET
                        logged_at   = %s,
                        meal_type   = %s,
                        dish_name   = %s,
                        kcal        = %s,
                        protein_g   = %s,
                        carbs_g     = %s,
                        fat_g       = %s,
                        fiber_g     = %s,
                        good_fat_g  = %s,
                        meat_g      = %s,
                        red_meat_g  = %s,
                        sodium_mg   = %s,
                        confidence  = %s,
                        notes       = %s,
                        updated_at  = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        validated["logged_at"],
                        validated["meal_type"],
                        validated["dish_name"],
                        validated["kcal"],
                        validated["protein_g"],
                        validated["carbs_g"],
                        validated["fat_g"],
                        validated["fiber_g"],
                        validated["good_fat_g"],
                        validated["meat_g"],
                        validated["red_meat_g"],
                        validated["sodium_mg"],
                        validated["confidence"],
                        validated["notes"],
                        entry_id,
                    ),
                )
                updated = dict(cur.fetchone())
            conn.commit()

    except psycopg2.errors.CheckViolation as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "DB_CONSTRAINT",
                    "message": "A database constraint was violated",
                    "detail": {"reason": str(exc).splitlines()[0]},
                    "request_id": uuid.uuid4().hex[:8],
                }
            },
        )
    except psycopg2.IntegrityError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "DB_CONSTRAINT",
                    "message": "A database integrity constraint was violated",
                    "detail": {"reason": str(exc).splitlines()[0]},
                    "request_id": uuid.uuid4().hex[:8],
                }
            },
        )

    row_dict = _serialise_overview_row(updated)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="food_entry",
            label="Meal Entries",
            total=1,
            page=1,
            page_size=1,
            row_actions=["delete", "copy"],
        ),
        **{"schema": ENTRIES_OVERVIEW_SCHEMA},
        rows=[row_dict],
    )

    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


@router.delete("/entries/{entry_id}", response_model=None)
def delete_entry(entry_id: str) -> Response:
    """
    DELETE /api/food/entries/{id} — hard-deletes one row from foodtracker.food_logs.
    Returns HTTP 204 No Content on success.
    Returns ApiError HTTP 404 if the row does not exist.

    Single-statement approach: execute DELETE, check cursor.rowcount — if 0,
    the row did not exist.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM foodtracker.food_logs WHERE id = %s",
                (entry_id,),
            )
            if cur.rowcount == 0:
                # Row did not exist — rollback implicitly on context exit,
                # then return 404. (DELETE of nothing is safe to rollback.)
                conn.rollback()
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": {
                            "code": "NOT_FOUND",
                            "message": f"Entry '{entry_id}' not found",
                            "detail": {"id": entry_id},
                            "request_id": uuid.uuid4().hex[:8],
                        }
                    },
                )
        conn.commit()

    return Response(status_code=204)


@router.post("/entries/{entry_id}/copy", response_model=None)
def copy_entry(entry_id: str) -> JSONResponse:
    """
    POST /api/food/entries/{id}/copy — copies one row from foodtracker.food_logs.
    The copy gets a new uuid4() id and logged_at = datetime.now().
    Returns the newly created row as an EntryDetail dict (HTTP 201).
    Returns ApiError HTTP 404 if the source row does not exist.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            # Read source row
            cur.execute(
                "SELECT * FROM foodtracker.food_logs WHERE id = %s",
                (entry_id,),
            )
            source = cur.fetchone()

        if source is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Entry '{entry_id}' not found",
                        "detail": {"id": entry_id},
                        "request_id": uuid.uuid4().hex[:8],
                    }
                },
            )

        source = dict(source)
        new_id = str(uuid.uuid4())
        new_logged_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO foodtracker.food_logs (
                    id, logged_at, meal_type, dish_name,
                    kcal, protein_g, carbs_g, fat_g, fiber_g, good_fat_g,
                    meat_g, red_meat_g, sodium_mg, confidence, notes,
                    standard, source_standard_id
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    FALSE, NULL
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
                ),
            )
            inserted = dict(cur.fetchone())
        conn.commit()

    return JSONResponse(
        status_code=201,
        content=_serialise_entry_detail(inserted),
    )
