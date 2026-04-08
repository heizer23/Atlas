"""
LinkingEngine — Pydantic models and shared data types.

Source of truth: 20_design/architecture.json shared_views
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel


# ── Shared data types ─────────────────────────────────────────────────────────

class ObjectRecord(BaseModel):
    object_id:    str
    workspace_id: str | None = None
    type:         str
    title:        str | None = None


class LinkRecord(BaseModel):
    link_id:          str
    from_object_id:   str
    to_object_id:     str
    relation_key:     str
    created_by_type:  str
    created_by_id:    str | None = None
    confidence:       float
    archived_at:      str | None = None
    created_at:       str


class LinkGroupItem(BaseModel):
    object_id: str
    type:      str
    title:     str | None = None


class LinkGroup(BaseModel):
    group_key: str
    label:     str
    items:     list[LinkGroupItem]


class RelationDefinition(BaseModel):
    key:                str
    forward_label:      str
    reverse_label:      str
    is_directional:     bool
    allowed_from_types: list[str]
    allowed_to_types:   list[str]
    is_active:          bool
    sort_order:         int


# ── Request bodies ─────────────────────────────────────────────────────────────

class CreateLinkRequest(BaseModel):
    source_object_id: str
    target_object_id: str
    relation_input:   str                # free-text; normalized to canonical key
    workspace_id:     str | None = None
    created_by_id:    str | None = None
    created_by_type:  str = "user"


class RegisterObjectRequest(BaseModel):
    object_id:    str
    object_type:  str
    workspace_id: str | None = None
    title:        str | None = None


# ── Response wrappers ─────────────────────────────────────────────────────────

class SearchObjectsResponse(BaseModel):
    objects: list[ObjectRecord]


class GetLinksResponse(BaseModel):
    links: list[LinkRecord]


class GetRelationDefinitionsResponse(BaseModel):
    relation_definitions: list[RelationDefinition]
