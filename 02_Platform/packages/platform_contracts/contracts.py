# platform_errorhandling/contracts.py
# Python implementation of the UI Dataset contract.
# Source of truth: 00_Blueprint/UI/01_UI_Contract
# Import from here in every router. Never redefine these types locally.

from typing import Any, Literal
from pydantic import BaseModel, Field

ColumnType = Literal["string", "number", "date", "boolean", "enum"]
RowAction  = Literal["delete", "edit", "copy"]


class ColumnSchema(BaseModel):
    key:            str
    label:          str
    type:           ColumnType
    sortable:       bool = True
    filterable:     bool = False
    detail_visible: bool = True
    format:         str | None = None


class DatasetMeta(BaseModel):
    object_type: str
    label:       str
    total:       int
    page:        int = 1
    page_size:   int = 25
    row_actions: list[RowAction] = []


class Dataset(BaseModel):
    meta:    DatasetMeta
    schema_: list[ColumnSchema] = Field(alias="schema")
    rows:    list[dict[str, Any]]

    model_config = {"populate_by_name": True}
