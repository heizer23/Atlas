"""
backend/routers/report.py

Sprint 02 — GET /api/food/report

Server-side bucket aggregation over foodtracker.food_logs.
No writes. Fully independent of food.py — shares no module-level state.

Server time choice: datetime.now() (local server time, not UTC) is used to
determine the current period for default resolution. This is consistent with
how logged_at is stored (no timezone) and avoids a mismatch between the
timestamp timezone and the query boundaries. If the server is UTC, both are UTC.
"""

import re
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

# REPORT_SCHEMA: column order matches the sprint definition Data Contract exactly.
# Key names must match Dataset row field keys exactly.
REPORT_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="bucket_label", label="Date",            type="string", sortable=False),
    ColumnSchema(key="kcal",         label="Calories (kcal)", type="number"),
    ColumnSchema(key="protein_g",    label="Protein (g)",     type="number"),
    ColumnSchema(key="carbs_g",      label="Carbs (g)",       type="number"),
    ColumnSchema(key="fat_g",        label="Fat (g)",         type="number"),
    ColumnSchema(key="fiber_g",      label="Fiber (g)",       type="number"),
]

# Period-key validation patterns by scope
_PERIOD_KEY_RE = {
    "year":  re.compile(r"^\d{4}$"),
    "month": re.compile(r"^\d{4}-\d{2}$"),
    "week":  re.compile(r"^\d{4}-W\d{2}$"),
}

# Month name abbreviations for year+aggregated bucket labels
_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ── Value object ──────────────────────────────────────────────────────────────

@dataclass
class ReportQuery:
    """
    Validated query parameters for GET /api/food/report.
    Only constructed by _parse_report_params() after all validation passes.
    """
    scope:      str
    period_key: str | None
    mode:       str


# ── Parameter validation ──────────────────────────────────────────────────────

def _parse_report_params(
    scope:      str,
    period_key: str | None,
    mode:       str,
) -> tuple["ReportQuery", None] | tuple[None, dict]:
    """
    Validate scope, mode, and period_key.

    Returns (ReportQuery, None) on success.
    Returns (None, error_dict) on any validation failure — the route handler
    turns this into an HTTP 422 JSONResponse.
    """

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

    # week scope only supports daily mode
    if scope == "week" and mode == "aggregated":
        return None, _err(
            "INVALID_PARAM",
            "mode=aggregated is not supported for scope=week; use mode=daily",
            {"field": "mode", "scope": "week"},
        )

    # all_time does not use period_key (ignore even if supplied)
    if scope == "all_time":
        return ReportQuery(scope=scope, period_key=None, mode=mode), None

    # All other scopes require period_key
    if period_key is None or period_key.strip() == "":
        return None, _err(
            "INVALID_PARAM",
            f"period_key is required for scope='{scope}'",
            {"field": "period_key", "scope": scope},
        )

    pattern = _PERIOD_KEY_RE[scope]
    if not pattern.match(period_key):
        expected = {
            "year":  "YYYY (e.g. '2025')",
            "month": "YYYY-MM (e.g. '2025-03')",
            "week":  "YYYY-WNN (e.g. '2025-W12')",
        }[scope]
        return None, _err(
            "INVALID_PERIOD_KEY",
            f"period_key '{period_key}' does not match expected format for scope='{scope}': {expected}",
            {"field": "period_key", "scope": scope, "expected_format": expected, "received": period_key},
        )

    return ReportQuery(scope=scope, period_key=period_key, mode=mode), None


# ── Bucket computation ────────────────────────────────────────────────────────

def _compute_buckets(
    query:   ReportQuery,
    db_rows: dict[str, dict] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """
    Returns (ordered_bucket_ids, bucket_label_map) for the given ReportQuery.

    For scope=all_time+aggregated: db_rows is required (must not be None).
    Bucket ids are the distinct year keys present in db_rows, sorted ascending.

    For scope=all_time+daily: returns ([], {}) — passthrough handled by _zero_fill.

    For all other scope+mode: db_rows is unused.

    bucket_label_map maps bucket_id → display string.
    """

    scope = query.scope
    mode  = query.mode

    # ── all_time ──────────────────────────────────────────────────────────────
    if scope == "all_time":
        if mode == "daily":
            # No enumerable period boundary; return empty — _zero_fill handles passthrough
            return [], {}
        else:
            # aggregated: years present in DB result only (no synthetic zero-fill)
            assert db_rows is not None, "_compute_buckets: db_rows required for all_time+aggregated"
            bucket_ids = sorted(db_rows.keys())
            label_map  = {bid: bid for bid in bucket_ids}  # label = 4-digit year string
            return bucket_ids, label_map

    # ── year ──────────────────────────────────────────────────────────────────
    if scope == "year":
        year = int(query.period_key)  # type: ignore[arg-type]
        if mode == "daily":
            # Every calendar day in the year
            start = date(year, 1, 1)
            end   = date(year + 1, 1, 1)
            days  = []
            cur   = start
            while cur < end:
                days.append(cur)
                cur += timedelta(days=1)
            bucket_ids = [d.strftime("%Y-%m-%d") for d in days]
            label_map  = {bid: str(d.day) for bid, d in zip(bucket_ids, days)}
            return bucket_ids, label_map
        else:
            # aggregated: one bucket per month in the year (YYYY-MM)
            bucket_ids = [f"{year:04d}-{m:02d}" for m in range(1, 13)]
            label_map  = {f"{year:04d}-{m:02d}": _MONTH_ABBR[m - 1] for m in range(1, 13)}
            return bucket_ids, label_map

    # ── month ─────────────────────────────────────────────────────────────────
    if scope == "month":
        y, m = map(int, query.period_key.split("-"))  # type: ignore[union-attr]
        month_start = date(y, m, 1)
        # First day of next month
        if m == 12:
            month_end = date(y + 1, 1, 1)
        else:
            month_end = date(y, m + 1, 1)

        if mode == "daily":
            days = []
            cur  = month_start
            while cur < month_end:
                days.append(cur)
                cur += timedelta(days=1)
            bucket_ids = [d.strftime("%Y-%m-%d") for d in days]
            label_map  = {bid: str(d.day) for bid, d in zip(bucket_ids, days)}
            return bucket_ids, label_map
        else:
            # aggregated: one bucket per ISO week that contains any day in this month.
            # We enumerate by walking day by day and collecting distinct ISO weeks.
            # The bucket id uses IYYY and IW (ISO year + ISO week number, zero-padded).
            seen:      list[str] = []
            label_map: dict[str, str] = {}
            cur = month_start
            while cur < month_end:
                iso = cur.isocalendar()
                # iso_year is the ISO year (may differ from calendar year at year boundary)
                bid   = f"{iso[0]:04d}-W{iso[1]:02d}"
                label = f"W{iso[1]:02d}"
                if bid not in seen:
                    seen.append(bid)
                    label_map[bid] = label
                cur += timedelta(days=1)
            return seen, label_map

    # ── week ──────────────────────────────────────────────────────────────────
    if scope == "week":
        # period_key format: YYYY-WNN  (e.g. "2025-W12")
        # mode must be daily (aggregated rejected in _parse_report_params)
        pk = query.period_key  # type: ignore[assignment]
        year_str, week_str = pk.split("-W")
        iso_year  = int(year_str)
        iso_week  = int(week_str)
        # ISO week starts on Monday; use the %G-%V-%u format trick
        monday = datetime.strptime(f"{iso_year}-{iso_week:02d}-1", "%G-%V-%u").date()
        days = [monday + timedelta(days=i) for i in range(7)]
        bucket_ids = [d.strftime("%Y-%m-%d") for d in days]
        label_map  = {bid: str(d.day) for bid, d in zip(bucket_ids, days)}
        return bucket_ids, label_map

    # Should not be reachable after _parse_report_params validation
    return [], {}


# ── WHERE clause builder ──────────────────────────────────────────────────────

def _build_where_clause(query: ReportQuery) -> tuple[str, list]:
    """
    Returns (sql_fragment, params) for the WHERE clause restricting
    foodtracker.food_logs to the selected period.

    all_time: empty fragment (no date filter).
    Other scopes compute inclusive start and exclusive end timestamps.
    """

    scope = query.scope

    if scope == "all_time":
        return "", []

    if scope == "year":
        year  = int(query.period_key)  # type: ignore[arg-type]
        start = date(year, 1, 1)
        end   = date(year + 1, 1, 1)
        return "WHERE logged_at >= %s AND logged_at < %s", [start, end]

    if scope == "month":
        y, m = map(int, query.period_key.split("-"))  # type: ignore[union-attr]
        start = date(y, m, 1)
        end   = date(y, m + 1, 1) if m < 12 else date(y + 1, 1, 1)
        return "WHERE logged_at >= %s AND logged_at < %s", [start, end]

    if scope == "week":
        pk = query.period_key  # type: ignore[assignment]
        year_str, week_str = pk.split("-W")
        iso_year = int(year_str)
        iso_week = int(week_str)
        monday = datetime.strptime(f"{iso_year}-{iso_week:02d}-1", "%G-%V-%u").date()
        sunday_end = monday + timedelta(days=7)  # exclusive upper bound (next Monday)
        return "WHERE logged_at >= %s AND logged_at < %s", [monday, sunday_end]

    return "", []


# ── GROUP BY key expression ───────────────────────────────────────────────────

def _build_group_key_expr(query: ReportQuery) -> str:
    """
    Returns the SQL expression for the GROUP BY key column.

    The expression must produce bucket_id strings that exactly match the format
    enumerated in _compute_buckets for the same scope+mode.

    Formats:
      daily (any scope)           → 'YYYY-MM-DD'  via to_char(logged_at,'YYYY-MM-DD')
      year+aggregated             → 'YYYY-MM'     via to_char(logged_at,'YYYY-MM')
      month+aggregated            → 'YYYY-WNN'    via to_char(logged_at,'IYYY-"W"IW')
                                    IYYY = ISO year, IW = ISO week 01-53
                                    Must NOT use WW (non-ISO, mismatches YYYY-WNN format)
      all_time+aggregated         → 'YYYY'        via to_char(logged_at,'YYYY')
    """

    scope = query.scope
    mode  = query.mode

    if mode == "daily":
        return "to_char(logged_at,'YYYY-MM-DD')"

    # aggregated paths
    if scope == "year":
        return "to_char(logged_at,'YYYY-MM')"

    if scope == "month":
        # ISO year and ISO week — must use IYYY (not YYYY) and IW (not WW)
        return "to_char(logged_at,'IYYY-\"W\"IW')"

    if scope == "all_time":
        return "to_char(logged_at,'YYYY')"

    # Should not be reached
    return "to_char(logged_at,'YYYY-MM-DD')"


# ── DB query ──────────────────────────────────────────────────────────────────

def _query_logs(
    query: ReportQuery,
    conn:  "psycopg2.extensions.connection",
) -> dict[str, dict]:
    """
    Execute SELECT with GROUP BY SUM over foodtracker.food_logs.

    Returns dict mapping bucket_id → {kcal, protein_g, carbs_g, fat_g, fiber_g}.

    NOTE: For scope=all_time+aggregated this function must be called before
    _compute_buckets because _compute_buckets requires the db_rows result to
    enumerate the distinct years that form the bucket list.
    """

    where_clause, params = _build_where_clause(query)
    group_expr           = _build_group_key_expr(query)

    sql = f"""
        SELECT
            {group_expr} AS bucket_id,
            SUM(kcal)      AS kcal,
            SUM(protein_g) AS protein_g,
            SUM(carbs_g)   AS carbs_g,
            SUM(fat_g)     AS fat_g,
            SUM(fiber_g)   AS fiber_g
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
            "kcal":      float(row["kcal"]      or 0),
            "protein_g": float(row["protein_g"] or 0),
            "carbs_g":   float(row["carbs_g"]   or 0),
            "fat_g":     float(row["fat_g"]      or 0),
            "fiber_g":   float(row["fiber_g"]    or 0),
        }

    return result


# ── Zero-fill and row assembly ────────────────────────────────────────────────

def _zero_fill(
    bucket_ids: list[str],
    label_map:  dict[str, str],
    db_rows:    dict[str, dict],
) -> list[dict]:
    """
    Merges the ordered bucket_ids list with db_rows into Dataset row dicts.

    Normal path (bucket_ids non-empty):
      For each bucket_id in the ordered list:
        - If present in db_rows: use those metric values.
        - Otherwise: emit a zero-value row.
      Attaches bucket_label from label_map.

    Passthrough path (bucket_ids empty — the all_time+daily case only):
      Emit one row per entry in db_rows, sorted ascending by bucket_id.
      Derives bucket_label as the day-of-month integer string from the
      YYYY-MM-DD bucket_id (e.g. '2025-03-07' → '7').
      label_map is empty in this case and must not be consulted.

    Returns ordered list of Dataset row dicts with keys:
      id, bucket_label, kcal, protein_g, carbs_g, fat_g, fiber_g
    """

    _zero: dict[str, Any] = {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0}

    if bucket_ids:
        # Normal path
        rows: list[dict] = []
        for bid in bucket_ids:
            metrics = db_rows.get(bid, _zero)
            rows.append({
                "id":           bid,
                "bucket_label": label_map[bid],
                "kcal":         metrics["kcal"],
                "protein_g":    metrics["protein_g"],
                "carbs_g":      metrics["carbs_g"],
                "fat_g":        metrics["fat_g"],
                "fiber_g":      metrics["fiber_g"],
            })
        return rows
    else:
        # Passthrough path: all_time+daily only
        # Emit DB rows in ascending bucket_id order; derive bucket_label from day-of-month
        rows = []
        for bid in sorted(db_rows.keys()):
            metrics = db_rows[bid]
            # Derive day-of-month from YYYY-MM-DD
            day_str = str(int(bid.split("-")[2]))  # "2025-03-07" → "7"
            rows.append({
                "id":           bid,
                "bucket_label": day_str,
                "kcal":         metrics["kcal"],
                "protein_g":    metrics["protein_g"],
                "carbs_g":      metrics["carbs_g"],
                "fat_g":        metrics["fat_g"],
                "fiber_g":      metrics["fiber_g"],
            })
        return rows


# ── Human-readable label ──────────────────────────────────────────────────────

def _build_report_label(query: ReportQuery) -> str:
    """
    Returns the human-readable DatasetMeta.label string.

    Examples:
      scope=month, period_key='2025-03', mode=daily     → 'March 2025 — Daily'
      scope=all_time, mode=aggregated                   → 'All Time — Aggregated'
      scope=year, period_key='2025', mode=daily         → '2025 — Daily'
      scope=year, period_key='2025', mode=aggregated    → '2025 — Aggregated'
      scope=month, period_key='2025-03', mode=aggregated→ 'March 2025 — Aggregated'
      scope=week, period_key='2025-W12', mode=daily     → 'Week 12, 2025 — Daily'
    """

    _MONTH_NAMES = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    mode_label = "Daily" if query.mode == "daily" else "Aggregated"

    if query.scope == "all_time":
        return f"All Time — {mode_label}"

    if query.scope == "year":
        return f"{query.period_key} — {mode_label}"

    if query.scope == "month":
        y, m = map(int, query.period_key.split("-"))  # type: ignore[union-attr]
        return f"{_MONTH_NAMES[m - 1]} {y} — {mode_label}"

    if query.scope == "week":
        # period_key: YYYY-WNN
        year_str, week_str = query.period_key.split("-W")  # type: ignore[union-attr]
        return f"Week {int(week_str)}, {year_str} — {mode_label}"

    return f"{query.period_key} — {mode_label}"


# ── Route handler ─────────────────────────────────────────────────────────────

@router.get("/report", response_model=None)
def get_report(
    scope:      str        = Query(...),
    period_key: str | None = Query(None),
    mode:       str        = Query(...),
) -> JSONResponse:
    """
    GET /api/food/report

    Validates params, queries foodtracker.food_logs with server-side aggregation,
    applies zero-fill bucket generation, and returns a Dataset.

    Orchestration order:
      - For scope=all_time+aggregated: call _query_logs() FIRST, then pass
        db_rows into _compute_buckets() so it can enumerate distinct years.
      - For all other scope+mode: call _compute_buckets() first, then _query_logs().
    """

    query, err = _parse_report_params(scope, period_key, mode)
    if err is not None:
        return JSONResponse(status_code=422, content=err)

    with get_db() as conn:
        # Determine call order based on scope+mode
        if query.scope == "all_time" and query.mode == "aggregated":
            # DB query must run first so _compute_buckets can enumerate years
            db_rows    = _query_logs(query, conn)
            bucket_ids, label_map = _compute_buckets(query, db_rows=db_rows)
        else:
            bucket_ids, label_map = _compute_buckets(query)
            db_rows    = _query_logs(query, conn)

    rows  = _zero_fill(bucket_ids, label_map, db_rows)
    label = _build_report_label(query)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="food_report_bucket",
            label=label,
            total=len(rows),
            page=1,
            page_size=len(rows),
            row_actions=[],
        ),
        **{"schema": REPORT_SCHEMA},
        rows=rows,
    )

    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))
