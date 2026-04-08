"""
NumericSeries — series and measurement CRUD router.

Endpoints:
  GET    /api/series
  POST   /api/series
  GET    /api/series/{label_id}
  DELETE /api/series/{label_id}
  POST   /api/series/{label_id}/measurements
  PATCH  /api/series/{label_id}/measurements/{id}
  DELETE /api/series/{label_id}/measurements/{id}

Source of truth: Sprint01/20_design/architecture.json interfaces.exposed_surfaces
"""

from __future__ import annotations

import uuid as _uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from backend.database import get_db
from backend.label_client import LabelClient, LabelClientError
from backend.models import (
    AddMeasurementRequest,
    CreateSeriesRequest,
    EditMeasurementRequest,
)
from backend.service import NumericSeriesError, NumericSeriesService
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter()
_svc = NumericSeriesService()
_label_client = LabelClient()


def _dataset_response(ds: Dataset) -> JSONResponse:
    return JSONResponse(content=ds.model_dump(by_alias=True, mode="json"))

# ── Column schemas ─────────────────────────────────────────────────────────────

LIST_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",               label="ID",              type="string",  sortable=False, filterable=False, detail_visible=False),
    ColumnSchema(key="label_name",       label="Label",           type="string",  sortable=True,  filterable=False),
    ColumnSchema(key="latest_value",     label="Latest Value",    type="number",  sortable=True,  filterable=False),
    ColumnSchema(key="sparkline_values", label="Sparkline",       type="string",  sortable=False, filterable=False),
]

DETAIL_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",          label="ID",          type="string",  sortable=False, filterable=False, detail_visible=False),
    ColumnSchema(key="value",       label="Value",       type="number",  sortable=True),
    ColumnSchema(key="recorded_at", label="Recorded At", type="date",    sortable=True),
]


# ── Series list ────────────────────────────────────────────────────────────────

@router.get("/series", response_model=None)
def list_series():
    """
    Return all tracked series sorted by label name.
    sparkline_values is a JSON-encoded float array (ColumnType: string).
    UI must use a custom list component — standard TableView is not suitable.
    """
    with get_db() as conn:
        rows = _svc.list_series_rows(conn)
    return _dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="numeric_series",
            label="Numeric Series",
            total=len(rows),
            page=1,
            page_size=len(rows) or 1,
            row_actions=["view"],
        ),
        **{"schema": LIST_SCHEMA, "rows": rows},
    ))


# ── Series create ──────────────────────────────────────────────────────────────

@router.post("/series", status_code=201)
def create_series(body: CreateSeriesRequest):
    """
    Create a new series.
    Step 1: create label via LabelEngine.
    Step 2: insert series record.
    Non-atomic: see architecture.json risks[0] for recovery path.
    """
    name = body.label_name.strip()
    if not name:
        return api_error("LABEL_NAME_EMPTY", "Label name must not be empty.", status=422)

    try:
        label = _label_client.create_label(name)
    except LabelClientError as exc:
        # Recovery path: if duplicate, LabelEngine returns LABEL_DUPLICATE_NAME.
        # Re-raise all errors including duplicate — caller must retry with existing label_id.
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message, "detail": None, "request_id": _uuid.uuid4().hex[:8]}},
        )

    label_id = label["id"]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO numeric_series.series (label_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (label_id,),
            )
        conn.commit()

    return JSONResponse(status_code=201, content={"label_id": label_id, "label_name": label["name"]})


# ── Series detail ──────────────────────────────────────────────────────────────

@router.get("/series/{label_id}", response_model=None)
def get_series(label_id: str):
    """Full measurement history for the series, sorted by recorded_at DESC."""
    with get_db() as conn:
        # Verify series exists
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM numeric_series.series WHERE label_id = %s",
                (label_id,),
            )
            if not cur.fetchone():
                return api_error("SERIES_NOT_FOUND", f"Series {label_id} not found.", status=404)

        rows = _svc.get_measurement_history(conn, label_id)

    return _dataset_response(Dataset(
        meta=DatasetMeta(
            object_type="measurement",
            label="Measurements",
            total=len(rows),
            page=1,
            page_size=len(rows) or 1,
            row_actions=["edit", "delete"],
        ),
        **{"schema": DETAIL_SCHEMA, "rows": rows},
    ))


# ── Series delete ──────────────────────────────────────────────────────────────

@router.delete("/series/{label_id}", status_code=204)
def delete_series(label_id: str):
    """
    Delete the series and all its measurements (cascade via FK).
    The LabelEngine label is NOT deleted.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM numeric_series.series WHERE label_id = %s RETURNING label_id",
                (label_id,),
            )
            if not cur.fetchone():
                conn.rollback()
                return api_error("SERIES_NOT_FOUND", f"Series {label_id} not found.", status=404)
        conn.commit()
    return Response(status_code=204)


# ── Add measurement ────────────────────────────────────────────────────────────

@router.post("/series/{label_id}/measurements", status_code=201)
def add_measurement(label_id: str, body: AddMeasurementRequest):
    """Add a new measurement entry to the series."""
    try:
        _svc.validate_measurement(body.value, body.recorded_at)
    except NumericSeriesError as exc:
        return api_error(exc.code, exc.message, status=exc.status)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM numeric_series.series WHERE label_id = %s",
                (label_id,),
            )
            if not cur.fetchone():
                return api_error("SERIES_NOT_FOUND", f"Series {label_id} not found.", status=404)

            cur.execute(
                """
                INSERT INTO numeric_series.measurements (label_id, value, recorded_at)
                VALUES (%s, %s, %s)
                RETURNING id::text, label_id::text, value, recorded_at::text
                """,
                (label_id, body.value, body.recorded_at),
            )
            row = cur.fetchone()
        conn.commit()

    return JSONResponse(
        status_code=201,
        content={"id": row["id"], "label_id": row["label_id"], "value": float(row["value"]), "recorded_at": row["recorded_at"]},
    )


# ── Edit measurement ───────────────────────────────────────────────────────────

@router.patch("/series/{label_id}/measurements/{measurement_id}")
def edit_measurement(label_id: str, measurement_id: str, body: EditMeasurementRequest):
    """Edit an existing measurement entry (value and/or recorded_at)."""
    if body.value is not None or body.recorded_at is not None:
        v = body.value if body.value is not None else 0.0
        r = body.recorded_at if body.recorded_at is not None else "2000-01-01T00:00:00"
        try:
            if body.value is not None:
                _svc.validate_measurement(body.value, r)
            if body.recorded_at is not None:
                _svc.validate_measurement(v, body.recorded_at)
        except NumericSeriesError as exc:
            return api_error(exc.code, exc.message, status=exc.status)

    with get_db() as conn:
        with conn.cursor() as cur:
            # Build dynamic update
            updates = []
            params = []
            if body.value is not None:
                updates.append("value = %s")
                params.append(body.value)
            if body.recorded_at is not None:
                updates.append("recorded_at = %s")
                params.append(body.recorded_at)

            if not updates:
                return api_error("NO_FIELDS", "No fields to update.", status=422)

            params.extend([measurement_id, label_id])
            cur.execute(
                f"""
                UPDATE numeric_series.measurements
                SET {", ".join(updates)}
                WHERE id = %s AND label_id = %s
                RETURNING id::text, label_id::text, value, recorded_at::text
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return api_error("MEASUREMENT_NOT_FOUND", "Measurement not found.", status=404)
        conn.commit()

    return JSONResponse(
        content={"id": row["id"], "label_id": row["label_id"], "value": float(row["value"]), "recorded_at": row["recorded_at"]},
    )


# ── Delete measurement ─────────────────────────────────────────────────────────

@router.delete("/series/{label_id}/measurements/{measurement_id}", status_code=204)
def delete_measurement(label_id: str, measurement_id: str):
    """Delete a single measurement entry."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM numeric_series.measurements WHERE id = %s AND label_id = %s RETURNING id",
                (measurement_id, label_id),
            )
            if not cur.fetchone():
                conn.rollback()
                return api_error("MEASUREMENT_NOT_FOUND", "Measurement not found.", status=404)
        conn.commit()
    return Response(status_code=204)
