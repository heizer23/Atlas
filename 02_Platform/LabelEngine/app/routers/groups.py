"""
LabelEngine — grouped object query route.

GET /api/groups   return objects grouped by primary label for a given object_type

Source of truth: 20_design/architecture.json interfaces.exposed_surfaces
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database import get_db
from app.models import GroupedObjectsResponse
from app.service import LabelService

router  = APIRouter()
_svc    = LabelService()


def _api_error(code: str, message: str, status: int = 400, detail=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code":       code,
                "message":    message,
                "detail":     detail,
                "request_id": uuid.uuid4().hex[:8],
            }
        },
    )


@router.get("/groups", response_model=GroupedObjectsResponse)
def get_grouped_objects(
    object_type: str | None = None,
    page:        int = 1,
    page_size:   int = 50,
):
    """
    Return objects grouped by primary label for the given object_type.

    Pagination model: paginate the flat ordered object list before grouping.
    meta.total = unpaginated count of all matching objects.
    meta.page_count = ceil(total / page_size).

    Returns 422 OBJECT_TYPE_REQUIRED if object_type is absent.
    """
    if not object_type:
        return _api_error(
            "OBJECT_TYPE_REQUIRED",
            "Query parameter 'object_type' is required.",
            status=422,
        )

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1

    with get_db() as conn:
        result = _svc.get_grouped_objects(conn, object_type, page, page_size)

    return result
