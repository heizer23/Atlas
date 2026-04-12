"""
NumericSeries — measurement catalog and batch ingestion router.

Endpoints:
  GET  /api/measurement-definitions  — return catalog as Dataset
  POST /api/measurements/batch       — atomic multi-measurement ingestion

Source of truth: Sprint03_Chronos&UXpt2/10_architecture.json internal_flow[1-3]
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.database import get_db
from backend.models import BatchMeasurementRequest
from backend.service import NumericSeriesService
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter()
_svc = NumericSeriesService()

# ── Catalog load ───────────────────────────────────────────────────────────────
# Load once at module import time. File lives next to the component root.
# Architecture: Sprint03/10_architecture.json §internal_flow[0] (catalog_load)

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "00_architecture" / "measurement_definitions.json"

try:
    with open(_CATALOG_PATH) as _f:
        _CATALOG_LIST: list[dict] = json.load(_f)
except FileNotFoundError as _exc:
    raise RuntimeError(
        f"measurement_definitions.json not found at {_CATALOG_PATH}. "
        "This file is required for NumericSeries to start."
    ) from _exc

# Build lookup dict: key → definition
_CATALOG: dict[str, dict] = {entry["key"]: entry for entry in _CATALOG_LIST}


# ── Catalog endpoint ───────────────────────────────────────────────────────────

_CATALOG_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="id",          label="Key",         type="string", sortable=True,  filterable=False),
    ColumnSchema(key="key",         label="Key",         type="string", sortable=True,  filterable=False, detail_visible=False),
    ColumnSchema(key="label",       label="Label",       type="string", sortable=True,  filterable=False),
    ColumnSchema(key="unit",        label="Unit",        type="string", sortable=False, filterable=False),
    ColumnSchema(key="value_type",  label="Type",        type="string", sortable=False, filterable=False),
    ColumnSchema(key="description", label="Description", type="string", sortable=False, filterable=False),
]


@router.get("/measurement-definitions", response_model=None)
def list_measurement_definitions():
    """
    Return all measurement definitions from the static catalog as a Dataset.
    Rows ordered by label ASC.
    """
    rows = sorted(
        [
            {
                "id": entry["key"],
                "key": entry["key"],
                "label": entry["label"],
                "unit": entry.get("unit") or "",
                "value_type": entry["value_type"],
                "description": entry["description"],
            }
            for entry in _CATALOG_LIST
        ],
        key=lambda r: r["label"].lower(),
    )

    ds = Dataset(
        meta=DatasetMeta(
            object_type="measurement_definition",
            label="Measurement Definitions",
            total=len(rows),
            page=1,
            page_size=len(rows) or 1,
            row_actions=[],
        ),
        **{"schema": _CATALOG_SCHEMA, "rows": rows},
    )
    return JSONResponse(content=ds.model_dump(by_alias=True, mode="json"))


# ── Batch ingestion endpoint ───────────────────────────────────────────────────

@router.post("/measurements/batch", status_code=201)
def batch_ingest(body: BatchMeasurementRequest):
    """
    Atomically insert multiple measurements in one request.

    Each entry references a catalog key (not a label_id). The endpoint:
    1. Validates recorded_at is valid ISO-8601
    2. Validates all keys exist in the catalog
    3. Validates all values are finite numbers
    4. Resolves each key → label_id via SQL join on labels.labels.name = key
    5. Verifies all keys have a corresponding series row
    6. Inserts all measurements in a single transaction
    7. Returns 201 {inserted: N}

    Architecture: Sprint03/10_architecture.json §internal_flow[2] (batch_ingestion)
    """
    # Step 1: validate recorded_at
    from datetime import datetime
    try:
        datetime.fromisoformat(body.recorded_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return api_error(
            "INVALID_TIMESTAMP",
            f"recorded_at must be a valid ISO-8601 timestamp, got: {body.recorded_at!r}",
            status=422,
        )

    if not body.measurements:
        return api_error("EMPTY_BATCH", "measurements list must not be empty.", status=422)

    # Step 2: validate all keys exist in catalog
    for entry in body.measurements:
        if entry.key not in _CATALOG:
            return api_error(
                "UNKNOWN_KEY",
                f"Measurement key '{entry.key}' is not in the catalog.",
                status=422,
            )

    # Step 3: validate all values are finite
    for entry in body.measurements:
        if not math.isfinite(entry.value):
            return api_error(
                "INVALID_VALUE",
                f"Measurement value for key '{entry.key}' must be a finite number.",
                status=422,
            )

    # Step 4: resolve keys to label_ids via SQL join
    keys = [entry.key for entry in body.measurements]

    with get_db() as conn:
        with conn.cursor() as cur:
            # Resolve all keys in one query: catalog key == label name
            cur.execute(
                """
                SELECT lower(l.name) AS key, s.label_id
                FROM numeric_series.series s
                JOIN labels.labels l ON l.id = s.label_id
                WHERE lower(l.name) = ANY(%s)
                """,
                ([k.lower() for k in keys],),
            )
            resolved = {row["key"]: row["label_id"] for row in cur.fetchall()}

        # Step 5: verify all keys have a series row
        for entry in body.measurements:
            if entry.key.lower() not in resolved:
                conn.rollback()
                return api_error(
                    "SERIES_NOT_FOUND",
                    f"No series found for measurement key '{entry.key}'. "
                    "Create the series first.",
                    status=422,
                )

        # Step 6: single-transaction insert
        try:
            with conn.cursor() as cur:
                for entry in body.measurements:
                    label_id = resolved[entry.key.lower()]
                    cur.execute(
                        """
                        INSERT INTO numeric_series.measurements (label_id, value, recorded_at)
                        VALUES (%s, %s, %s)
                        """,
                        (label_id, entry.value, body.recorded_at),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return JSONResponse(
        status_code=201,
        content={"inserted": len(body.measurements)},
    )
