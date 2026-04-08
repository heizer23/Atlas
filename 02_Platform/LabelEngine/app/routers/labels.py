"""
LabelEngine — label search and creation routes.

GET  /api/labels       search labels by prefix
POST /api/labels       create a new label

Source of truth: 20_design/architecture.json interfaces.exposed_surfaces
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database import get_db
from app.models import CreateLabelRequest, LabelRecord, LabelSearchResponse
from app.service import LabelEngineError, LabelService

router  = APIRouter()
_svc    = LabelService()


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


@router.get("/labels", response_model=LabelSearchResponse)
def search_labels(q: str = "") -> LabelSearchResponse:
    """
    Search labels by case-insensitive name prefix.
    Empty q returns all labels.
    """
    with get_db() as conn:
        labels = _svc.search_labels(conn, q)
    return LabelSearchResponse(labels=labels)


@router.post("/labels", response_model=LabelRecord, status_code=201)
def create_label(body: CreateLabelRequest):
    """
    Create a new label.
    Returns 422 LABEL_NAME_EMPTY if name is blank after stripping whitespace.
    """
    name = body.name.strip()
    if not name:
        return _api_error("LABEL_NAME_EMPTY", "Label name must not be empty.", status=422)

    try:
        with get_db() as conn:
            label = _svc.create_label(conn, name)
    except LabelEngineError as exc:
        return _api_error(exc.code, exc.message, exc.status)

    return label
