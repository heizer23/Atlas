import json
import uuid
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.errors
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.database import get_db
from platform_errorhandling import api_error
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/food", tags=["food"])

# ── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack", "drink", "other"}

TEMPLATE_JSON = """{
  "timestamp": "2026-03-20T12:30:00",
  "meal_type": "lunch",
  "base_quantity": 200,
  "items": [
    {
      "name": "chicken breast",
      "quantity": 200,
      "unit": "g"
    }
  ],
  "nutrition": {
    "calories_kcal": 165,
    "protein_g": 31,
    "carbs_g": 0,
    "fat_g": 3.6,
    "fiber_g": 0,
    "good_fat_g": 0,
    "meat_g": 100,
    "red_meat_g": 0,
    "sodium_mg": 74,
    "alcohol_g": 0
  },
  "confidence": 4,
  "notes": "nutrition values are per 100 units of base_quantity; omit base_quantity to log absolute values (base_quantity defaults to 100)"
}"""

MEAL_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="logged_at",  label="Date / Time",   type="date",   sortable=True),
    ColumnSchema(key="meal_type",  label="Meal",           type="string", sortable=True,  filterable=True),
    ColumnSchema(key="dish_name",  label="Dish",           type="string", sortable=True),
    ColumnSchema(key="kcal",       label="kcal",           type="number", sortable=True,  format="kcal"),
    ColumnSchema(key="protein_g",  label="Protein (g)",    type="number", sortable=True,  format="g"),
    ColumnSchema(key="carbs_g",    label="Carbs (g)",      type="number", sortable=True,  format="g"),
    ColumnSchema(key="fat_g",      label="Fat (g)",        type="number", sortable=True,  format="g"),
    ColumnSchema(key="fiber_g",    label="Fiber (g)",      type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="good_fat_g", label="Good Fat (g)",   type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="meat_g",     label="Meat (g)",       type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="red_meat_g", label="Red Meat (g)",   type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="sodium_mg",  label="Sodium (mg)",    type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="confidence", label="Confidence",     type="number", sortable=True),
    ColumnSchema(key="notes",      label="Notes",          type="string", sortable=False, detail_visible=True),
]

# ── Validation and normalisation ───────────────────────────────────────────────

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


def _validate_and_normalise(body: bytes) -> tuple[dict, None] | tuple[None, dict]:
    """
    Decode and validate raw request bytes, then normalise.

    Returns (normalised_dict, None) on success.
    Returns (None, error_dict) on any failure — error_dict is ApiError-shaped;
    the route handler constructs the JSONResponse (HTTP 422) from it.

    Validation order:
      1. JSON parse
      2. timestamp parseable as ISO-8601
      3. meal_type in allowed enum
      4. items non-empty array, each item has non-empty name
      5. nutrition object present
      6. required numeric fields present and >= 0
      7. optional numeric fields satisfy individual >= 0 check if present;
         cross-field checks (good_fat_g <= fat_g, red_meat_g <= meat_g)
         run only after both operands individually pass (applied to per-100g
         values when base_quantity is present)
      8. confidence integer 1–5 if present
      9. optional top-level base_quantity: number > 0 if present; when present,
         scale all nutrition.* as stored_value = ref_value * base_quantity / 100.
         When absent, base_quantity defaults to 100 (values stored as-is).
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

    # Step 2 — timestamp
    raw_ts = data.get("timestamp")
    if raw_ts is None:
        return None, _err(
            "VALIDATION_ERROR",
            "timestamp is required",
            "timestamp",
            "MISSING_FIELD: field is absent",
        )
    try:
        parsed_ts = datetime.fromisoformat(str(raw_ts))
    except ValueError:
        return None, _err(
            "VALIDATION_ERROR",
            f"timestamp '{raw_ts}' is not a valid ISO-8601 datetime",
            "timestamp",
            "INVALID_FIELD: must be ISO-8601 datetime e.g. '2026-03-20T12:30:00'",
        )

    # Step 3 — meal_type
    raw_meal_type = data.get("meal_type")
    if raw_meal_type is None:
        return None, _err(
            "VALIDATION_ERROR",
            "meal_type is required",
            "meal_type",
            "MISSING_FIELD: field is absent",
        )
    meal_type = str(raw_meal_type).strip().lower()
    if meal_type not in ALLOWED_MEAL_TYPES:
        return None, _err(
            "VALIDATION_ERROR",
            f"meal_type '{meal_type}' is not allowed",
            "meal_type",
            f"INVALID_FIELD: must be one of {sorted(ALLOWED_MEAL_TYPES)}",
        )

    # Step 4 — items
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or len(raw_items) == 0:
        return None, _err(
            "VALIDATION_ERROR",
            "items must be a non-empty array",
            "items",
            "INVALID_FIELD: must be a non-empty array",
        )
    normalised_items = []
    for i, item in enumerate(raw_items):
        if not isinstance(item, dict):
            return None, _err(
                "VALIDATION_ERROR",
                f"items[{i}] must be an object",
                f"items[{i}]",
                "INVALID_FIELD: each item must be a JSON object",
            )
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, _err(
                "VALIDATION_ERROR",
                f"items[{i}].name must be a non-empty string",
                f"items[{i}].name",
                "INVALID_FIELD: name is absent or empty",
            )
        normalised_item: dict[str, Any] = {"name": name.strip()}
        qty = item.get("quantity")
        if qty is not None:
            if not isinstance(qty, (int, float)) or qty <= 0:
                return None, _err(
                    "VALIDATION_ERROR",
                    f"items[{i}].quantity must be a number > 0",
                    f"items[{i}].quantity",
                    "INVALID_FIELD: quantity must be > 0 when present",
                )
            normalised_item["quantity"] = qty
        unit = item.get("unit")
        if unit is not None:
            normalised_item["unit"] = str(unit)
        normalised_items.append(normalised_item)

    # Step 5 — nutrition object present
    nutrition = data.get("nutrition")
    if not isinstance(nutrition, dict):
        return None, _err(
            "VALIDATION_ERROR",
            "nutrition object is required",
            "nutrition",
            "MISSING_FIELD: nutrition object is absent",
        )

    # Step 6 — required numeric fields: calories_kcal, protein_g, carbs_g, fat_g
    required_num_fields = [
        ("nutrition.calories_kcal", nutrition.get("calories_kcal")),
        ("nutrition.protein_g",     nutrition.get("protein_g")),
        ("nutrition.carbs_g",       nutrition.get("carbs_g")),
        ("nutrition.fat_g",         nutrition.get("fat_g")),
    ]
    for field_path, val in required_num_fields:
        if val is None:
            return None, _err(
                "VALIDATION_ERROR",
                f"{field_path} is required",
                field_path,
                "MISSING_FIELD: field is absent",
            )
        if not isinstance(val, (int, float)) or val < 0:
            return None, _err(
                "VALIDATION_ERROR",
                f"{field_path} must be a number >= 0",
                field_path,
                "INVALID_FIELD: must be a non-negative number",
            )

    calories_kcal = nutrition["calories_kcal"]
    protein_g     = float(nutrition["protein_g"])
    carbs_g       = float(nutrition["carbs_g"])
    fat_g         = float(nutrition["fat_g"])

    # Step 7 — optional numeric fields: individual >= 0 checks first, then cross-field
    # Each optional field is checked for type and >= 0 before cross-field validation.

    def _check_optional_nonneg(key: str, raw_val: Any) -> tuple[float | None, dict | None]:
        """Return (float_value, None) or (None, error_dict)."""
        if raw_val is None:
            return None, None
        if not isinstance(raw_val, (int, float)) or raw_val < 0:
            return None, _err(
                "VALIDATION_ERROR",
                f"nutrition.{key} must be a number >= 0",
                f"nutrition.{key}",
                "INVALID_FIELD: must be a non-negative number when present",
            )
        return float(raw_val), None

    fiber_val,    fiber_err    = _check_optional_nonneg("fiber_g",    nutrition.get("fiber_g"))
    if fiber_err:
        return None, fiber_err

    good_fat_val, good_fat_err = _check_optional_nonneg("good_fat_g", nutrition.get("good_fat_g"))
    if good_fat_err:
        return None, good_fat_err

    meat_val,     meat_err     = _check_optional_nonneg("meat_g",     nutrition.get("meat_g"))
    if meat_err:
        return None, meat_err

    red_meat_val, red_meat_err = _check_optional_nonneg("red_meat_g", nutrition.get("red_meat_g"))
    if red_meat_err:
        return None, red_meat_err

    sodium_val,   sodium_err   = _check_optional_nonneg("sodium_mg",  nutrition.get("sodium_mg"))
    if sodium_err:
        return None, sodium_err

    alcohol_val,  alcohol_err  = _check_optional_nonneg("alcohol_g",  nutrition.get("alcohol_g"))
    if alcohol_err:
        return None, alcohol_err

    # Cross-field checks — only reachable when both operands individually passed
    if good_fat_val is not None and good_fat_val > fat_g:
        return None, _err(
            "VALIDATION_ERROR",
            f"nutrition.good_fat_g ({good_fat_val}) must be <= fat_g ({fat_g})",
            "nutrition.good_fat_g",
            "INVALID_FIELD: good_fat_g must be <= fat_g",
        )

    if red_meat_val is not None and meat_val is not None and red_meat_val > meat_val:
        return None, _err(
            "VALIDATION_ERROR",
            f"nutrition.red_meat_g ({red_meat_val}) must be <= meat_g ({meat_val})",
            "nutrition.red_meat_g",
            "INVALID_FIELD: red_meat_g must be <= meat_g",
        )
    # Edge case: red_meat_g present but meat_g absent — defaults to 0; red_meat_g > 0 violates <= meat_g
    if red_meat_val is not None and meat_val is None and red_meat_val > 0:
        return None, _err(
            "VALIDATION_ERROR",
            f"nutrition.red_meat_g ({red_meat_val}) must be <= meat_g (0)",
            "nutrition.red_meat_g",
            "INVALID_FIELD: red_meat_g must be <= meat_g",
        )

    # Step 8 — confidence
    raw_conf = data.get("confidence")
    if raw_conf is not None:
        if not isinstance(raw_conf, int) or isinstance(raw_conf, bool) or not (1 <= raw_conf <= 5):
            return None, _err(
                "VALIDATION_ERROR",
                f"confidence must be an integer between 1 and 5",
                "confidence",
                "INVALID_FIELD: must be integer in range [1, 5]",
            )
        confidence = raw_conf
    else:
        confidence = 3

    # ── Normalise ─────────────────────────────────────────────────────────────

    # Apply defaults for optional numeric fields
    fiber_g    = fiber_val    if fiber_val    is not None else 0.0
    good_fat_g = good_fat_val if good_fat_val is not None else 0.0
    meat_g     = meat_val     if meat_val     is not None else 0.0
    red_meat_g = red_meat_val if red_meat_val is not None else 0.0
    sodium_mg  = sodium_val   if sodium_val   is not None else 0.0
    alcohol_g  = alcohol_val  if alcohol_val  is not None else 0.0

    # Derive dish_name by joining items[].name with ", "
    dish_name = ", ".join(item["name"] for item in normalised_items)

    # Cast kcal to integer (round)
    kcal = int(round(calories_kcal))

    # Re-serialise timestamp as "YYYY-MM-DDTHH:MM:SS" (strip microseconds/tzinfo for preview)
    logged_at = parsed_ts.strftime("%Y-%m-%dT%H:%M:%S")

    # notes — nullable free text
    notes = data.get("notes")
    if notes is not None:
        notes = str(notes)

    # Step 9 — optional base_quantity: when present, treat nutrition.* as per-100g
    # reference values and scale before storing. When absent, default to 100
    # (values stored as-is; base_quantity=100 means "macros are for 100 units").
    raw_bq = data.get("base_quantity")
    base_quantity: float = 100.0
    if raw_bq is not None:
        if not isinstance(raw_bq, (int, float)) or isinstance(raw_bq, bool) or raw_bq <= 0:
            return None, _err(
                "VALIDATION_ERROR",
                "base_quantity must be a number > 0",
                "base_quantity",
                "INVALID_FIELD: base_quantity must be a positive number when present",
            )
        base_quantity = float(raw_bq)
        # Scale all macro values from per-100g to the consumed quantity.
        # Cross-field checks above were applied to per-100g values — correct.
        factor = base_quantity / 100.0
        kcal       = int(round(calories_kcal * factor))
        protein_g  = round(protein_g  * factor, 1)
        carbs_g    = round(carbs_g    * factor, 1)
        fat_g      = round(fat_g      * factor, 1)
        fiber_g    = round(fiber_g    * factor, 1)
        good_fat_g = round(good_fat_g * factor, 1)
        meat_g     = round(meat_g     * factor, 1)
        red_meat_g = round(red_meat_g * factor, 1)
        sodium_mg  = round(sodium_mg  * factor, 1)
        alcohol_g  = round(alcohol_g  * factor, 1)

    normalised: dict[str, Any] = {
        "logged_at":     logged_at,
        "meal_type":     meal_type,
        "dish_name":     dish_name,
        "items":         normalised_items,
        "kcal":          kcal,
        "protein_g":     protein_g,
        "carbs_g":       carbs_g,
        "fat_g":         fat_g,
        "fiber_g":       fiber_g,
        "good_fat_g":    good_fat_g,
        "meat_g":        meat_g,
        "red_meat_g":    red_meat_g,
        "sodium_mg":     sodium_mg,
        "alcohol_g":     alcohol_g,
        "confidence":    confidence,
        "notes":         notes,
        "base_quantity": base_quantity,
    }

    return normalised, None


# ── Route handlers ─────────────────────────────────────────────────────────────

@router.get("/template", response_model=None)
def get_template() -> PlainTextResponse:
    """Return the canonical meal JSON template as text/plain."""
    return PlainTextResponse(content=TEMPLATE_JSON)


@router.post("/validate", response_model=None)
async def validate_meal(request: Request) -> JSONResponse:
    """Validate and normalise the pasted JSON; return preview model or ApiError."""
    body = await request.body()
    normalised, err = _validate_and_normalise(body)
    if err is not None:
        return JSONResponse(status_code=422, content=err)
    return JSONResponse(content={"preview": normalised})


@router.post("/meals", response_model=None)
async def commit_meal(request: Request) -> JSONResponse:
    """Validate, insert one row into foodtracker.food_logs, return Dataset."""
    body = await request.body()
    normalised, err = _validate_and_normalise(body)
    if err is not None:
        return JSONResponse(status_code=422, content=err)

    row_id = str(uuid.uuid4())

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO foodtracker.food_logs (
                        id, logged_at, meal_type, dish_name,
                        kcal, protein_g, carbs_g, fat_g, fiber_g, good_fat_g,
                        meat_g, red_meat_g, sodium_mg, alcohol_g, confidence, notes,
                        base_quantity
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s
                    ) RETURNING *
                    """,
                    (
                        row_id,
                        normalised["logged_at"],
                        normalised["meal_type"],
                        normalised["dish_name"],
                        normalised["kcal"],
                        normalised["protein_g"],
                        normalised["carbs_g"],
                        normalised["fat_g"],
                        normalised["fiber_g"],
                        normalised["good_fat_g"],
                        normalised["meat_g"],
                        normalised["red_meat_g"],
                        normalised["sodium_mg"],
                        normalised["alcohol_g"],
                        normalised["confidence"],
                        normalised["notes"],
                        normalised["base_quantity"],
                    ),
                )
                inserted = dict(cur.fetchone())
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

    # Serialise inserted row for Dataset: id and logged_at as str, numerics as float.
    # psycopg2 returns TIMESTAMP columns as datetime objects; use strftime to
    # guarantee "YYYY-MM-DDTHH:MM:SS" format (str() would produce a space separator).
    raw_logged_at = inserted["logged_at"]
    logged_at_str = (
        raw_logged_at.strftime("%Y-%m-%dT%H:%M:%S")
        if hasattr(raw_logged_at, "strftime")
        else str(raw_logged_at)
    )

    row: dict[str, Any] = {
        "id":         str(inserted["id"]),
        "logged_at":  logged_at_str,
        "meal_type":  inserted["meal_type"],
        "dish_name":  inserted["dish_name"],
        "kcal":       float(inserted["kcal"]),
        "protein_g":  float(inserted["protein_g"]),
        "carbs_g":    float(inserted["carbs_g"]),
        "fat_g":      float(inserted["fat_g"]),
        "fiber_g":    float(inserted["fiber_g"]),
        "good_fat_g": float(inserted["good_fat_g"]),
        "meat_g":     float(inserted["meat_g"]),
        "red_meat_g": float(inserted["red_meat_g"]),
        "sodium_mg":  float(inserted["sodium_mg"]),
        "confidence": int(inserted["confidence"]),
        "notes":      inserted["notes"],
    }

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="food_meal",
            label="Food Log",
            total=1,
            page=1,
            page_size=1,
            row_actions=[],
        ),
        **{"schema": MEAL_SCHEMA},
        rows=[row],
    )

    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))
