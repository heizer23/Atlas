"""
PreferenceStore — all preference HTTP endpoints.

GET    /api/preferences/{scope}/{key}  retrieve one preference (Dataset, one row) or 404
PUT    /api/preferences/{scope}/{key}  upsert a preference (200, PreferenceRecord)
DELETE /api/preferences/{scope}/{key}  remove a preference (204, idempotent)
GET    /api/preferences/{scope}        retrieve all preferences for scope (Dataset)

Source of truth: Sprint01_Init/10_architecture.json interfaces.exposed_surfaces
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.database import get_db
from app.models import PreferenceRecord, PutPreferenceRequest

try:
    from platform_contracts.contracts import ColumnSchema, Dataset, DatasetMeta
except ImportError:
    from platform_contracts.contracts import ColumnSchema, Dataset, DatasetMeta  # type: ignore

router = APIRouter()

# Dataset schema emitted for all GET preference endpoints
_PREF_COLUMNS = [
    ColumnSchema(key="scope",      label="Scope",      type="text",     sortable=True,  filterable=False),
    ColumnSchema(key="key",        label="Key",         type="text",     sortable=True,  filterable=False),
    ColumnSchema(key="value",      label="Value",       type="text",     sortable=False, filterable=False),
    ColumnSchema(key="updated_at", label="Updated At",  type="datetime", sortable=True,  filterable=False),
]


def _api_error(code: str, message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code":       code,
                "message":    message,
                "detail":     None,
                "request_id": uuid.uuid4().hex[:8],
            }
        },
    )


def _validate_scope_key(scope: str, key: str | None = None) -> JSONResponse | None:
    """Return 422 ApiError if scope or key is empty or whitespace-only."""
    if not scope or not scope.strip():
        return _api_error("INVALID_SCOPE", "scope must not be empty or whitespace-only.", status=422)
    if key is not None and (not key or not key.strip()):
        return _api_error("INVALID_KEY", "key must not be empty or whitespace-only.", status=422)
    return None


def _row_from_record(record: dict) -> dict:
    """Convert a DB row dict to a Dataset row dict."""
    return {
        "scope":      record["scope"],
        "key":        record["key"],
        "value":      json.dumps(record["value_json"]),  # serialize JSON value for display
        "updated_at": record["updated_at"].isoformat(),
    }


@router.get("/preferences/{scope}/{key}")
def get_preference(scope: str, key: str):
    """
    Retrieve a single preference by scope and key.
    Returns Dataset (one row) or 404 ApiError.
    """
    err = _validate_scope_key(scope, key)
    if err:
        return err

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT scope, key, value_json, updated_at "
                "FROM preferences.preferences "
                "WHERE scope = %s AND key = %s",
                (scope, key),
            )
            row = cur.fetchone()

    if row is None:
        return _api_error("PREFERENCE_NOT_FOUND", f"No preference found for scope='{scope}' key='{key}'.", status=404)

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="preference",
            label=f"Preference: {scope}/{key}",
            total=1,
            page=1,
            page_size=1,
            row_actions=[],
        ),
        **{"schema": _PREF_COLUMNS},
        rows=[_row_from_record(row)],
    )
    return dataset


@router.put("/preferences/{scope}/{key}", response_model=PreferenceRecord)
def put_preference(scope: str, key: str, body: PutPreferenceRequest):
    """
    Create or overwrite a preference (upsert).
    Returns 200 with the stored record.
    """
    err = _validate_scope_key(scope, key)
    if err:
        return err

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO preferences.preferences (scope, key, value_json, updated_at)
                VALUES (%s, %s, %s::jsonb, now())
                ON CONFLICT (scope, key)
                DO UPDATE SET value_json = EXCLUDED.value_json, updated_at = now()
                RETURNING scope, key, value_json, updated_at
                """,
                (scope, key, json.dumps(body.value)),
            )
            row = cur.fetchone()
        conn.commit()

    return PreferenceRecord(
        scope=row["scope"],
        key=row["key"],
        value=row["value_json"],
        updated_at=row["updated_at"],
    )


@router.delete("/preferences/{scope}/{key}", status_code=204)
def delete_preference(scope: str, key: str):
    """
    Remove a preference. Idempotent — returns 204 whether or not it existed.
    """
    err = _validate_scope_key(scope, key)
    if err:
        return err

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM preferences.preferences WHERE scope = %s AND key = %s",
                (scope, key),
            )
        conn.commit()

    return Response(status_code=204)


@router.get("/preferences/{scope}")
def get_preferences_by_scope(scope: str):
    """
    Retrieve all preferences for a scope.
    Returns Dataset. Empty rows list if no preferences exist for scope.
    """
    err = _validate_scope_key(scope)
    if err:
        return err

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT scope, key, value_json, updated_at "
                "FROM preferences.preferences "
                "WHERE scope = %s "
                "ORDER BY key",
                (scope,),
            )
            rows = cur.fetchall()

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="preference",
            label=f"Preferences: {scope}",
            total=len(rows),
            page=1,
            page_size=len(rows) if rows else 25,
            row_actions=[],
        ),
        **{"schema": _PREF_COLUMNS},
        rows=[_row_from_record(r) for r in rows],
    )
    return dataset
