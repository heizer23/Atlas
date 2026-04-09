"""
LabelEngine — Pydantic models and shared data types.

Source of truth: 20_design/architecture.json shared_views
"""

from __future__ import annotations

from pydantic import BaseModel


# ── Shared data types ─────────────────────────────────────────────────────────

class LabelRecord(BaseModel):
    id:   str
    name: str


class ObjectLabelRecord(BaseModel):
    object_id:   str
    label_id:    str
    label_name:  str
    attached_at: str  # ISO-8601


class GroupItem(BaseModel):
    id:            str
    primary_label: str | None
    labels:        list[str]


class LabelGroup(BaseModel):
    label: str
    items: list[GroupItem]


class GroupedMeta(BaseModel):
    total:      int
    page:       int
    page_size:  int
    page_count: int


# ── Response envelopes ────────────────────────────────────────────────────────

class LabelSearchResponse(BaseModel):
    labels: list[LabelRecord]


class ObjectLabelsResponse(BaseModel):
    labels: list[ObjectLabelRecord]


class GroupedObjectsResponse(BaseModel):
    meta:   GroupedMeta
    groups: list[LabelGroup]


# ── Request bodies ────────────────────────────────────────────────────────────

class CreateLabelRequest(BaseModel):
    name: str


class AttachLabelRequest(BaseModel):
    label_name:  str
    object_type: str  # caller-supplied; must be lowercase (DB CHECK constraint enforces)


# ── Batch read models ─────────────────────────────────────────────────────────

class BatchLabelRecord(BaseModel):
    id:          str
    name:        str
    attached_at: str  # ISO-8601


class BatchLabelsRequest(BaseModel):
    object_ids:  list[str]
    object_type: str


class BatchLabelsResponse(BaseModel):
    labels: dict[str, list[BatchLabelRecord]]
