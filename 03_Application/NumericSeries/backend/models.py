"""
NumericSeries — Pydantic request and response models.

Source of truth: Sprint01/20_design/scaffolding.json models.py
No domain logic in this file.
"""

from __future__ import annotations

from pydantic import BaseModel


# ── Request bodies ────────────────────────────────────────────────────────────

class CreateSeriesRequest(BaseModel):
    label_name: str


class AddMeasurementRequest(BaseModel):
    value: float
    recorded_at: str  # ISO-8601


class EditMeasurementRequest(BaseModel):
    value: float | None = None
    recorded_at: str | None = None  # ISO-8601


class BatchReadRequest(BaseModel):
    label_ids: list[str]


class ExternalWriteEntry(BaseModel):
    value: float
    recorded_at: str  # ISO-8601


class ExternalWriteRequest(BaseModel):
    entries: list[ExternalWriteEntry]


# ── Response bodies ───────────────────────────────────────────────────────────

class MeasurementRecord(BaseModel):
    id: str
    label_id: str
    value: float
    recorded_at: str


class SeriesRecord(BaseModel):
    label_id: str
    label_name: str


class BatchSeriesEntry(BaseModel):
    label_id: str
    label_name: str | None  # None when label_id not found in LabelEngine
    measurements: list[MeasurementRecord]


class BatchReadResponse(BaseModel):
    series: list[BatchSeriesEntry]


class ExternalWriteResponse(BaseModel):
    inserted: int
