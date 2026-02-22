"""
FoodTracker domain tools.

Plain functions — no FastMCP dependency.
Registered into 02_Platform/MCPGateway at startup.
"""
import os
import uuid
from datetime import datetime
from typing import Optional

import psycopg
from psycopg.rows import dict_row


# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

def _pg():
    """Open a Postgres connection using Atlas platform env vars."""
    return psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("ATLAS_PG_PORT", 5432)),
        dbname=os.environ["ATLAS_PG_DB"],
        user=os.environ["ATLAS_PG_USER"],
        password=os.environ["ATLAS_PG_PASSWORD"],
        row_factory=dict_row,
    )


def _to_json(row: dict) -> dict:
    """Convert a psycopg row to a JSON-safe dict (handles Decimal, UUID, datetime)."""
    out = {}
    for k, v in row.items():
        if v is None or isinstance(v, (int, float, str, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def log_meal(
    dish_name: str,
    meal_type: str,
    kcal: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    fiber_g: float = 0.0,
    good_fat_g: float = 0.0,
    meat_g: float = 0.0,
    red_meat_g: float = 0.0,
    sodium_mg: float = 0.0,
    confidence: int = 3,
    notes: Optional[str] = None,
    logged_at: Optional[str] = None,
) -> dict:
    """
    Record a meal in the food log.

    meal_type: prefer one of breakfast | lunch | dinner | snack | other
    kcal, protein_g, carbs_g, fat_g: required nutritional estimates.
    fiber_g, good_fat_g, meat_g, red_meat_g, sodium_mg: optional, default 0.
    good_fat_g must be ≤ fat_g. red_meat_g must be ≤ meat_g.
    confidence: 1 (rough conversational guess) to 5 (exact from food label).
      Typical AI estimate: 2–3.
    logged_at: ISO datetime string e.g. "2026-02-22T19:00:00". Defaults to now.

    Returns the inserted row.
    """
    ts = datetime.fromisoformat(logged_at) if logged_at else datetime.now()
    row_id = str(uuid.uuid4())

    with _pg() as con, con.cursor() as cur:
        cur.execute(
            """
            INSERT INTO food_logs (
                id, logged_at, meal_type, dish_name,
                kcal, protein_g, carbs_g, fiber_g, fat_g, good_fat_g,
                meat_g, red_meat_g, sodium_mg, confidence, notes
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            ) RETURNING *;
            """,
            (
                row_id, ts, meal_type, dish_name,
                kcal, protein_g, carbs_g, fiber_g, fat_g, good_fat_g,
                meat_g, red_meat_g, sodium_mg, confidence, notes,
            ),
        )
        row = cur.fetchone()
        con.commit()

    return _to_json(row)


def get_nutrition_summary(from_date: str, to_date: str) -> dict:
    """
    Get aggregated nutrition totals and daily averages for a time period.

    from_date: ISO date string e.g. "2026-02-01" (inclusive)
    to_date:   ISO date string e.g. "2026-02-22" (inclusive)

    Returns:
      - period: the queried date range
      - totals: summed nutritional values across all meals in the period
      - daily_averages: totals divided by the number of days that have data
      - meals: list of meals logged in the period (summary fields only)
    """
    interval = "logged_at >= %s::date AND logged_at < %s::date + INTERVAL '1 day'"

    with _pg() as con, con.cursor() as cur:

        # Aggregated totals
        cur.execute(
            f"""
            SELECT
                COUNT(*)                         AS meal_count,
                COUNT(DISTINCT DATE(logged_at))  AS day_count,
                COALESCE(SUM(kcal),        0)    AS total_kcal,
                COALESCE(SUM(protein_g),   0)    AS total_protein_g,
                COALESCE(SUM(carbs_g),     0)    AS total_carbs_g,
                COALESCE(SUM(fiber_g),     0)    AS total_fiber_g,
                COALESCE(SUM(fat_g),       0)    AS total_fat_g,
                COALESCE(SUM(good_fat_g),  0)    AS total_good_fat_g,
                COALESCE(SUM(meat_g),      0)    AS total_meat_g,
                COALESCE(SUM(red_meat_g),  0)    AS total_red_meat_g,
                COALESCE(SUM(sodium_mg),   0)    AS total_sodium_mg
            FROM food_logs
            WHERE {interval}
            """,
            (from_date, to_date),
        )
        agg = cur.fetchone()

        meal_count = int(agg["meal_count"])
        day_count  = int(agg["day_count"]) or 1

        totals = {k: round(float(v), 1) for k, v in agg.items()
                  if k not in ("day_count",)}
        totals["meal_count"] = meal_count
        totals["day_count"]  = int(agg["day_count"])

        daily_averages = {
            f"avg_{k[6:]}": round(float(v) / day_count, 1)
            for k, v in agg.items()
            if k.startswith("total_")
        }

        # Meal list — lightweight summary
        cur.execute(
            f"""
            SELECT id::text, logged_at::text, meal_type, dish_name,
                   kcal, protein_g, carbs_g, fat_g, confidence
            FROM food_logs
            WHERE {interval}
            ORDER BY logged_at
            """,
            (from_date, to_date),
        )
        meals = [_to_json(r) for r in cur.fetchall()]

    return {
        "period": {"from": from_date, "to": to_date},
        "totals": totals,
        "daily_averages": daily_averages,
        "meals": meals,
    }
