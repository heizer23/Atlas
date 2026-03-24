---
RULE_ID: R-CON-BP-04
TITLE: UI Data Contract
TYPE: CONSTITUTIONAL
SCOPE: BLUEPRINT
STATUS: ACTIVE
VERSION: v1.0
CANONICAL_SOURCE: .claude/rules/R-CON-BP-04_ui_data_contract.md
RELATES_TO: R-CON-BP-02
---

Status: Stable — changes deliberately, with explicit versioning.
Audience: LLMs writing backend endpoints, LLMs designing frontend-facing interfaces, LLMs implementing frontend data consumption, humans reviewing backend/UI contracts.
Relationship: Defines the stable data contract between Atlas producers and Atlas UI consumers. Application and platform code couple to this contract, not to concrete frontend implementation details.

Purpose

Any Atlas endpoint or interface intended to supply data for UI rendering must return a payload that conforms to a stable UI data contract.

Applications and platform components are coupled to this contract. They are not coupled to React components, hooks, local view logic, or styling choices.

This contract exists so that:

backend producers know exactly what shape to return

frontend consumers know exactly what shape to expect

design agents can define interfaces without coupling to implementation details

UI implementation can evolve without breaking producers

This document defines data shape and payload semantics only.

It does not define:

rendering behavior

placeholder behavior

visual fallback behavior

Scope

This contract applies to:

application endpoints that provide UI-rendered data

platform components that expose frontend-facing data interfaces

frontend components that consume Atlas data payloads

This contract does not apply to:

internal implementation details of frontend components

styling or visual design rules

runtime rendering fallback behavior

endpoints governed by another explicit stable contract

Core Rule

Any Atlas endpoint or interface intended to supply data for UI rendering must return a payload defined by an explicit stable UI contract.

The default contract for collection-style UI data is:

Dataset

or ApiError

Other UI payload shapes are allowed only when Dataset is not a natural fit and the alternate shape is defined as an explicit stable contract.

Default-First Rule

Use Dataset by default for:

tables

list views

filterable collections

chart source data

pageable result sets

Do not invent an alternate contract when Dataset fits reasonably well.

Define another explicit UI contract when the payload is primarily:

a command result

a form definition or submission result

a detail object with nested structure

a tree or graph

a composed dashboard payload

live or streaming state

1. Core Types
1.1 TypeScript (frontend)
// src/api/types.ts
// Single source of truth for frontend contract types.
// Do not redefine locally.

export type ColumnType =
  | "string"
  | "number"
  | "date"
  | "boolean"
  | "enum"
  | string; // extensible

export type Aggregation =
  | "sum"
  | "avg"
  | "count"
  | "max"
  | "min";

export type BarMode =
  | "grouped"
  | "stacked"
  | "stacked_percent";

export type SeriesType =
  | "bar"
  | "line";

export type YAxis =
  | "left"
  | "right";

export type RowAction = string; // e.g. "edit", "delete", "archive"

export interface ColumnSchema {
  key: string;
  label: string;
  type: ColumnType;

  sortable?: boolean;
  filterable?: boolean;
  detail_visible?: boolean;

  format?: string;
}

export interface DatasetMeta {
  object_type: string;
  label: string;

  total: number;

  page: number;
  page_size: number;

  row_actions: RowAction[];
}

export type Row =
  { id: string } &
  Record<string, unknown>;

export interface Dataset {
  meta: DatasetMeta;
  schema: ColumnSchema[];
  rows: Row[];
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    detail?: unknown;
    request_id: string;
  };
}
1.2 Python (backend)
# backend/platform/models.py
# Import from here in routers and platform services. Never redefine locally.

from typing import Any, Literal
from pydantic import BaseModel, Field


ColumnType = str
Aggregation = Literal["sum", "avg", "count", "max", "min"]
RowAction = str


class ColumnSchema(BaseModel):
    key: str
    label: str
    type: ColumnType

    sortable: bool = True
    filterable: bool = False
    detail_visible: bool = True

    format: str | None = None


class DatasetMeta(BaseModel):
    object_type: str
    label: str

    total: int

    page: int = 1
    page_size: int = 25

    row_actions: list[RowAction] = Field(default_factory=list)


class Dataset(BaseModel):
    meta: DatasetMeta
    schema: list[ColumnSchema]
    rows: list[dict[str, Any]]
2. Dataset Semantics

The following rules are part of the contract.

Rule	Meaning
Every row must contain id: string	Stable row identity for UI actions and detail rendering
schema order defines column display order	Producers control display ordering
schema[].key must match row field keys exactly	Field matching is case-sensitive
Row fields not present in schema are non-contract data	Consumers may ignore them
row_actions is declared by the producer	The frontend must not invent object actions
total represents the total number of rows matching the query before pagination is applied	Pagination metadata refers to the full result set
3. Chart Mapping Types

Charts are views over a Dataset.
They do not define their own independent data shape.

3.1 BarChartMapping
interface BarChartMapping {
  x: string;
  y: string;

  aggregation: Aggregation;

  group_by?: string;
  bar_mode?: BarMode;
}
3.2 LineChartMapping
interface LineChartMapping {
  x: string;
  y: string;

  aggregation: Aggregation;
}
3.3 ComboChartMapping
interface SeriesMapping {
  y: string;

  type: SeriesType;

  label?: string;

  aggregation: Aggregation;

  y_axis?: YAxis;
}

interface ComboChartMapping {
  x: string;
  series: SeriesMapping[];
}
4. Error Envelope

All UI-facing errors must use this shape:

{
  "error": {
    "code": "INVALID_FILTER",
    "message": "Filter field 'exercis' does not exist in schema",
    "detail": { "field": "exercis", "available": ["exercise", "date", "sets"] },
    "request_id": "req_8f2a1c"
  }
}

Rules:

code is machine-readable

message is human-readable

detail is optional developer/debug context

request_id is required for traceability

5. Canonical Producer Rule

A backend endpoint or platform interface that provides UI-rendered data must:

declare a stable Dataset.meta.object_type

declare a complete schema

return rows whose keys conform to that schema

return ApiError when contract-valid data cannot be produced

6. Canonical Endpoint Example
from platform.models import Dataset, DatasetMeta, ColumnSchema

@router.get("/workout/sessions")
def list_sessions(page: int = 1, page_size: int = 25) -> Dataset:

    rows, total = db.get_sessions(page=page, page_size=page_size)

    return Dataset(
        meta=DatasetMeta(
            object_type="workout_session",
            label="Workout Sessions",
            total=total,
            page=page,
            page_size=page_size,
            row_actions=["edit", "delete"],
        ),
        schema=[
            ColumnSchema(key="date", label="Date", type="date"),
            ColumnSchema(key="exercise", label="Exercise", type="string", filterable=True),
            ColumnSchema(key="volume_kg", label="Volume (kg)", type="number", format="kg"),
            ColumnSchema(key="notes", label="Notes", type="string", sortable=False),
        ],
        rows=rows,
    )
7. Contract Boundaries
Producers must not

couple payload shape to specific React components

require frontend knowledge of backend-local model names

invent app-local response shapes when Dataset fits

return ad hoc error formats

Consumers must not

assume undeclared row fields are stable

hardcode actions that are not declared in row_actions

reinterpret schema keys or change their meaning locally

8. Out of Scope

This document does not define:

placeholder rendering

validation warning rendering

chart fallback behavior

visual design

layout rules

component composition details

form runtime behavior

Those belong in separate UI implementation or primitive behavior rules.

9. Guidance for Designers

When a designer agent defines a frontend-facing platform or application interface:

use this contract as the default payload contract for UI-rendered data

reference this contract instead of restating field definitions

surface any required deviation explicitly as an open question or controlled exception

Do not silently invent alternate UI payload contracts.

10. Versioning

This contract is versioned.
The current version is v1.0.

Changes require:

explicit decision

update to this document

corresponding updates to affected producers and consumers

version bump in this header

Compatibility rules:

Change	Breaking
Add optional field	No
Add optional schema metadata	No
Remove field	Yes
Rename field	Yes
Change semantics	Yes
