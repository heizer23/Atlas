"""
backend/routers/report.py

Sprint 05 — GET /api/food/report

Rolling-window bucket aggregation over foodtracker.food_logs.

Changes from Sprint 02:
- Removed period_key parameter. Periods are now rolling (week=7d, month=30d, year=365d).
- New per-meal-type breakdown columns:
    kcal_breakfast, kcal_lunch, kcal_dinner, kcal_snack, kcal_alcohol, kcal_total
    protein_breakfast, protein_lunch, protein_dinner, protein_snack, protein_total
  kcal_alcohol = kcal for entries where alcohol_g > 0 (pseudo-meal-type, not a new meal_type value).
- Year scope: returns kcal_avg / protein_avg per bucket row (rolling avg over reported days only).
- reported_days added to dataset meta extras (count of distinct days with at least one entry).
- week scope: supports aggregated mode (removed the old restriction).
- Mode selector retained; week now supports both daily and aggregated.

Server time: datetime.now() (local server time, no timezone) — consistent with how logged_at is stored.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import psycopg2.extensions
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.database import get_db
from platform_contracts import ColumnSchema, Dataset, DatasetMeta

router = APIRouter(prefix="/food", tags=["report"])

# ── Constants ──────────────────────────────────────────────────────────────────

VALID_SCOPES = {"all_time", "year", "month", "week"}
VALID_MODES  = {"aggregated", "daily"}

# Month name abbreviations for aggregated bucket labels
_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# REPORT_SCHEMA: column order per sprint definition §3.6.
REPORT_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="bucket_label",      label="Date",                  type="string", sortable=False),
    ColumnSchema(key="kcal_breakfast",    label="Breakfast kcal",        type="number"),
    ColumnSchema(key="kcal_lunch",        label="Lunch kcal",            type="number"),
    ColumnSchema(key="kcal_dinner",       label="Dinner kcal",           type="number"),
    ColumnSchema(key="kcal_snack",        label="Snacks kcal",           type="number"),
    ColumnSchema(key="kcal_alcohol",      label="Drink kcal",            type="number"),
    ColumnSchema(key="kcal_total",        label="Total kcal",            type="number"),
    ColumnSchema(key="protein_breakfast", label="Breakfast protein (g)", type="number"),
    ColumnSchema(key="protein_lunch",     label="Lunch protein (g)",     type="number"),
    ColumnSchema(key="protein_dinner",    label="Dinner protein (g)",    type="number"),
    ColumnSchema(key="protein_snack",     label="Snacks protein (g)",    type="number"),
    ColumnSchema(key="protein_total",     label="Total protein (g)",     type="number"),
]

# Year scope adds running average columns — emitted in rows but not in base schema
# (frontend renders them via ComboChart mapping, not as table columns)


# ── Value object ──────────────────────────────────────────────────────────────

@dataclass
class ReportQuery:
    """Validated query parameters for GET /api/food/report."""
    scope: str
    mode:  str


# ── Parameter validation ──────────────────────────────────────────────────────

def _parse_report_params(
    scope: str,
    mode:  str,
) -> tuple["ReportQuery", None] | tuple[None, dict]:
    def _err(code: str, message: str, detail: Any = None) -> dict:
        return {
            "error": {
                "code": code,
                "message": message,
                "detail": detail,
                "request_id": uuid.uuid4().hex[:8],
            }
        }

    if scope not in VALID_SCOPES:
        return None, _err(
            "INVALID_PARAM",
            f"scope '{scope}' is not valid; must be one of {sorted(VALID_SCOPES)}",
            {"field": "scope", "received": scope},
        )

    if mode not in VALID_MODES:
        return None, _err(
            "INVALID_PARAM",
            f"mode '{mode}' is not valid; must be one of {sorted(VALID_MODES)}",
            {"field": "mode", "received": mode},
        )

    return ReportQuery(scope=scope, mode=mode), None


# ── Rolling window ────────────────────────────────────────────────────────────

def _rolling_window(scope: str) -> tuple[date, date]:
    """
    Returns (start_date, end_date) for the rolling window.
    end_date is today (inclusive). start_date is today - N + 1.

    week:  last 7 days  (today - 6 ... today)
    month: last 30 days (today - 29 ... today)
    year:  last 365 days (today - 364 ... today)
    all_time: returns (date.min, today) — caller ignores for all_time
    """
    today = date.today()
    if scope == "week":
        return today - timedelta(days=6), today
    if scope == "month":
        return today - timedelta(days=29), today
    if scope == "year":
        return today - timedelta(days=364), today
    # all_time — no date boundary
    return date.min, today


# ── Bucket enumeration ────────────────────────────────────────────────────────

def _compute_buckets(
    query:   ReportQuery,
    db_rows: dict[str, dict] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """
    Returns (ordered_bucket_ids, bucket_label_map).

    For all_time + aggregated: db_rows required — enumerate distinct years present.
    For all_time + daily: passthrough — returns ([], {}).
    For rolling scopes (week, month, year): enumerate all calendar days in window.
      - daily mode: one bucket per day (YYYY-MM-DD), label = day-of-month
      - aggregated mode:
          week  → one bucket per day (same as daily — 7 days is daily granularity)
          month → one bucket per ISO week containing any day in the window
          year  → one bucket per calendar month in the window
    """

    scope = query.scope
    mode  = query.mode

    # ── all_time ──────────────────────────────────────────────────────────────
    if scope == "all_time":
        if mode == "daily":
            return [], {}
        else:
            assert db_rows is not None
            bucket_ids = sorted(db_rows.keys())
            label_map  = {bid: bid for bid in bucket_ids}
            return bucket_ids, label_map

    start, end = _rolling_window(scope)

    # ── Enumerate calendar days in window ─────────────────────────────────────
    days: list[date] = []
    cur  = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)

    if mode == "daily" or scope == "week":
        # day-level granularity for all rolling scopes in daily mode,
        # and for week scope even in aggregated mode (7 days is already daily)
        bucket_ids = [d.strftime("%Y-%m-%d") for d in days]
        label_map  = {bid: str(d.day) for bid, d in zip(bucket_ids, days)}
        return bucket_ids, label_map

    # aggregated paths for month and year
    if scope == "month":
        # One bucket per ISO week containing any day in the 30-day window
        seen:      list[str] = []
        label_map: dict[str, str] = {}
        for d in days:
            iso = d.isocalendar()
            bid   = f"{iso[0]:04d}-W{iso[1]:02d}"
            label = f"W{iso[1]:02d}"
            if bid not in seen:
                seen.append(bid)
                label_map[bid] = label
        return seen, label_map

    if scope == "year":
        # One bucket per calendar month in the 365-day window
        seen_months: list[str] = []
        label_map_m: dict[str, str] = {}
        for d in days:
            bid   = f"{d.year:04d}-{d.month:02d}"
            label = _MONTH_ABBR[d.month - 1]
            if bid not in seen_months:
                seen_months.append(bid)
                label_map_m[bid] = label
        return seen_months, label_map_m

    return [], {}


# ── GROUP BY key expression ───────────────────────────────────────────────────

def _build_group_key_expr(query: ReportQuery) -> str:
    """SQL expression for GROUP BY key — must match bucket_id format from _compute_buckets."""
    scope = query.scope
    mode  = query.mode

    if mode == "daily" or scope in ("week", "all_time"):
        # day-level or all_time-daily passthrough: YYYY-MM-DD
        if scope == "all_time" and mode == "aggregated":
            return "to_char(logged_at,'YYYY')"
        return "to_char(logged_at,'YYYY-MM-DD')"

    # aggregated paths
    if scope == "month":
        return "to_char(logged_at,'IYYY-\"W\"IW')"

    if scope == "year":
        return "to_char(logged_at,'YYYY-MM')"

    return "to_char(logged_at,'YYYY-MM-DD')"


# ── WHERE clause ──────────────────────────────────────────────────────────────

def _build_where_clause(query: ReportQuery) -> tuple[str, list]:
    """Returns (sql_fragment, params) restricting to the selected rolling window."""
    scope = query.scope

    if scope == "all_time":
        return "", []

    start, end = _rolling_window(scope)
    # inclusive start, inclusive end (end is today, so < tomorrow)
    end_exclusive = end + timedelta(days=1)
    return "WHERE logged_at >= %s AND logged_at < %s", [start, end_exclusive]


# ── DB query ──────────────────────────────────────────────────────────────────

def _query_logs(
    query: ReportQuery,
    conn:  "psycopg2.extensions.connection",
) -> dict[str, dict]:
    """
    Execute SELECT with GROUP BY SUM, broken down by meal_type + alcohol_g.

    Returns dict mapping bucket_id → {
        kcal_breakfast, kcal_lunch, kcal_dinner, kcal_snack, kcal_alcohol, kcal_total,
        protein_breakfast, protein_lunch, protein_dinner, protein_snack, protein_total,
        reported_days  (count of distinct calendar days with at least one entry in bucket)
    }

    kcal_alcohol = SUM(kcal) WHERE alcohol_g > 0 (pseudo-meal-type, not tied to meal_type).
    """

    where_clause, params = _build_where_clause(query)
    group_expr           = _build_group_key_expr(query)

    sql = f"""
        SELECT
            {group_expr} AS bucket_id,
            SUM(CASE WHEN meal_type = 'breakfast' AND (alcohol_g = 0 OR alcohol_g IS NULL) THEN kcal ELSE 0 END) AS kcal_breakfast,
            SUM(CASE WHEN meal_type = 'lunch'     AND (alcohol_g = 0 OR alcohol_g IS NULL) THEN kcal ELSE 0 END) AS kcal_lunch,
            SUM(CASE WHEN meal_type = 'dinner'    AND (alcohol_g = 0 OR alcohol_g IS NULL) THEN kcal ELSE 0 END) AS kcal_dinner,
            SUM(CASE WHEN meal_type = 'snack'     AND (alcohol_g = 0 OR alcohol_g IS NULL) THEN kcal ELSE 0 END) AS kcal_snack,
            SUM(CASE WHEN alcohol_g > 0                                                    THEN kcal ELSE 0 END) AS kcal_alcohol,
            SUM(kcal) AS kcal_total,
            SUM(CASE WHEN meal_type = 'breakfast' AND (alcohol_g = 0 OR alcohol_g IS NULL) THEN protein_g ELSE 0 END) AS protein_breakfast,
            SUM(CASE WHEN meal_type = 'lunch'     AND (alcohol_g = 0 OR alcohol_g IS NULL) THEN protein_g ELSE 0 END) AS protein_lunch,
            SUM(CASE WHEN meal_type = 'dinner'    AND (alcohol_g = 0 OR alcohol_g IS NULL) THEN protein_g ELSE 0 END) AS protein_dinner,
            SUM(CASE WHEN meal_type = 'snack'     AND (alcohol_g = 0 OR alcohol_g IS NULL) THEN protein_g ELSE 0 END) AS protein_snack,
            SUM(protein_g) AS protein_total,
            COUNT(DISTINCT logged_at::date) AS reported_days
        FROM foodtracker.food_logs
        {where_clause}
        GROUP BY {group_expr}
        ORDER BY {group_expr}
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    result: dict[str, dict] = {}
    for row in rows:
        bid = str(row["bucket_id"])
        result[bid] = {
            "kcal_breakfast":    float(row["kcal_breakfast"]    or 0),
            "kcal_lunch":        float(row["kcal_lunch"]        or 0),
            "kcal_dinner":       float(row["kcal_dinner"]       or 0),
            "kcal_snack":        float(row["kcal_snack"]        or 0),
            "kcal_alcohol":      float(row["kcal_alcohol"]      or 0),
            "kcal_total":        float(row["kcal_total"]        or 0),
            "protein_breakfast": float(row["protein_breakfast"] or 0),
            "protein_lunch":     float(row["protein_lunch"]     or 0),
            "protein_dinner":    float(row["protein_dinner"]    or 0),
            "protein_snack":     float(row["protein_snack"]     or 0),
            "protein_total":     float(row["protein_total"]     or 0),
            "reported_days":     int(row["reported_days"]       or 0),
        }

    return result


def _total_reported_days(query: ReportQuery, conn: "psycopg2.extensions.connection") -> int:
    """Count distinct calendar days with at least one entry in the whole window."""
    where_clause, params = _build_where_clause(query)
    sql = f"""
        SELECT COUNT(DISTINCT logged_at::date) AS n
        FROM foodtracker.food_logs
        {where_clause}
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return int(row["n"] or 0) if row else 0


# ── Zero-fill and row assembly ────────────────────────────────────────────────

_ZERO_METRICS: dict[str, Any] = {
    "kcal_breakfast":    0,
    "kcal_lunch":        0,
    "kcal_dinner":       0,
    "kcal_snack":        0,
    "kcal_alcohol":      0,
    "kcal_total":        0,
    "protein_breakfast": 0,
    "protein_lunch":     0,
    "protein_dinner":    0,
    "protein_snack":     0,
    "protein_total":     0,
    "reported_days":     0,
}


def _zero_fill(
    bucket_ids:   list[str],
    label_map:    dict[str, str],
    db_rows:      dict[str, dict],
    include_avgs: bool = False,
) -> list[dict]:
    """
    Merge ordered bucket_ids with db_rows into Dataset row dicts.

    Normal path (bucket_ids non-empty):
      Emits one row per bucket_id; zero-fills missing buckets.

    Passthrough path (bucket_ids empty — all_time + daily):
      Emits one row per db_rows entry, sorted ascending by bucket_id.
      Derives bucket_label as day-of-month from YYYY-MM-DD key.

    For year scope (include_avgs=True):
      Appends kcal_avg and protein_avg per row = rolling cumulative average
      over reported days only (cumulative sum ÷ cumulative reported_days count).
    """

    def _make_row(bid: str, label: str, metrics: dict) -> dict:
        row: dict[str, Any] = {
            "id":                bid,
            "bucket_label":      label,
            "kcal_breakfast":    metrics["kcal_breakfast"],
            "kcal_lunch":        metrics["kcal_lunch"],
            "kcal_dinner":       metrics["kcal_dinner"],
            "kcal_snack":        metrics["kcal_snack"],
            "kcal_alcohol":      metrics["kcal_alcohol"],
            "kcal_total":        metrics["kcal_total"],
            "protein_breakfast": metrics["protein_breakfast"],
            "protein_lunch":     metrics["protein_lunch"],
            "protein_dinner":    metrics["protein_dinner"],
            "protein_snack":     metrics["protein_snack"],
            "protein_total":     metrics["protein_total"],
        }
        return row

    if bucket_ids:
        rows = [
            _make_row(bid, label_map[bid], db_rows.get(bid, _ZERO_METRICS))
            for bid in bucket_ids
        ]
    else:
        # Passthrough: all_time + daily
        rows = []
        for bid in sorted(db_rows.keys()):
            day_str = str(int(bid.split("-")[2]))  # "2025-03-07" → "7"
            rows.append(_make_row(bid, day_str, db_rows[bid]))

    if include_avgs:
        # Cumulative rolling average over reported days only
        cumulative_kcal    = 0.0
        cumulative_protein = 0.0
        cumulative_days    = 0
        for i, (row, bid) in enumerate(zip(rows, bucket_ids if bucket_ids else sorted(db_rows.keys()))):
            metrics = db_rows.get(bid, _ZERO_METRICS)
            cumulative_kcal    += metrics["kcal_total"]
            cumulative_protein += metrics["protein_total"]
            cumulative_days    += metrics["reported_days"]
            if cumulative_days > 0:
                row["kcal_avg"]    = round(cumulative_kcal    / cumulative_days, 1)
                row["protein_avg"] = round(cumulative_protein / cumulative_days, 1)
            else:
                row["kcal_avg"]    = 0.0
                row["protein_avg"] = 0.0

    return rows


# ── Human-readable label ──────────────────────────────────────────────────────

def _build_report_label(query: ReportQuery) -> str:
    today = date.today()
    mode_label = "Daily" if query.mode == "daily" else "Aggregated"

    if query.scope == "all_time":
        return f"All Time — {mode_label}"

    start, end = _rolling_window(query.scope)
    if query.scope == "week":
        return f"Last 7 Days ({start} – {end}) — {mode_label}"
    if query.scope == "month":
        return f"Last 30 Days ({start} – {end}) — {mode_label}"
    if query.scope == "year":
        return f"Last 365 Days ({start} – {end}) — {mode_label}"

    return f"{query.scope} — {mode_label}"


# ── Route handler ─────────────────────────────────────────────────────────────

@router.get("/report", response_model=None)
def get_report(
    scope: str = Query(...),
    mode:  str = Query(...),
) -> JSONResponse:
    """
    GET /api/food/report

    Query params:
      scope — required: all_time | week | month | year
      mode  — required: daily | aggregated

    Returns a Dataset with per-meal-type breakdown columns.
    For year scope: rows also include kcal_avg and protein_avg fields.
    Dataset meta includes reported_days (count of distinct days with entries in window).
    """

    query, err = _parse_report_params(scope, mode)
    if err is not None:
        return JSONResponse(status_code=422, content=err)

    include_avgs = (query.scope == "year")

    with get_db() as conn:
        if query.scope == "all_time" and query.mode == "aggregated":
            # DB query first so _compute_buckets can enumerate distinct years
            db_rows              = _query_logs(query, conn)
            bucket_ids, label_map = _compute_buckets(query, db_rows=db_rows)
        else:
            bucket_ids, label_map = _compute_buckets(query)
            db_rows              = _query_logs(query, conn)

        reported_days = _total_reported_days(query, conn)

    rows  = _zero_fill(bucket_ids, label_map, db_rows, include_avgs=include_avgs)
    label = _build_report_label(query)

    # Determine schema — year scope gets avg columns appended
    schema = list(REPORT_SCHEMA)
    if include_avgs:
        schema = schema + [
            ColumnSchema(key="kcal_avg",    label="Avg daily kcal",      type="number"),
            ColumnSchema(key="protein_avg", label="Avg daily protein (g)", type="number"),
        ]

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="food_report_bucket",
            label=label,
            total=len(rows),
            page=1,
            page_size=len(rows),
            row_actions=[],
        ),
        **{"schema": schema},
        rows=rows,
    )

    # Include reported_days as extra field in meta-level extras via the response dict
    response_dict = dataset.model_dump(by_alias=True, mode="json")
    response_dict["meta"]["reported_days"] = reported_days

    return JSONResponse(content=response_dict)
