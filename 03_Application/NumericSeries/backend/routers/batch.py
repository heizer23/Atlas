"""
NumericSeries — batch read and external write router.

Endpoints:
  POST /api/batch/series          — batch read for OpenClaw
  POST /api/series/{label_id}/values — external write for OpenClaw

Source of truth: Sprint01/20_design/architecture.json interfaces.exposed_surfaces
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.models import BatchReadRequest, ExternalWriteRequest
from backend.service import NumericSeriesError, NumericSeriesService
from platform_errorhandling import api_error

router = APIRouter()
_svc = NumericSeriesService()


# ── Batch read ─────────────────────────────────────────────────────────────────

@router.post("/batch/series")
def batch_read(body: BatchReadRequest):
    """
    Batch read: return measurements for a list of label_ids.
    Returns a result entry for every requested label_id including empty series.
    label_name is null for label_ids not found in LabelEngine.
    Not a Dataset — external contract for OpenClaw.
    """
    with get_db() as conn:
        series = _svc.assemble_batch(conn, body.label_ids)
    return {"series": series}


# ── External write ─────────────────────────────────────────────────────────────

@router.post("/series/{label_id}/values")
def external_write(label_id: str, body: ExternalWriteRequest):
    """
    External write endpoint for OpenClaw: append one or more measurements
    to an existing series.

    Open question resolution: if label_id is not found in numeric_series.series,
    return 404 SERIES_NOT_FOUND (conservative default matching architecture.json
    failure_modes).
    """
    with get_db() as conn:
        # Verify series exists
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM numeric_series.series WHERE label_id = %s",
                (label_id,),
            )
            if not cur.fetchone():
                return api_error("SERIES_NOT_FOUND", f"Series {label_id} not found.", status=404)

        # Validate and insert all entries
        inserted = 0
        for entry in body.entries:
            try:
                _svc.validate_measurement(entry.value, entry.recorded_at)
            except NumericSeriesError as exc:
                return api_error(exc.code, exc.message, status=exc.status)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO numeric_series.measurements (label_id, value, recorded_at)
                    VALUES (%s, %s, %s)
                    """,
                    (label_id, entry.value, entry.recorded_at),
                )
            inserted += 1

        conn.commit()

    return JSONResponse(content={"inserted": inserted})
