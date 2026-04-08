"""
LabelEngine — label attachment and retrieval routes.

POST   /api/objects/{object_id}/labels              attach a label to an object
DELETE /api/objects/{object_id}/labels/{label_id}   remove a label from an object
GET    /api/objects/{object_id}/labels              get all labels for an object

Source of truth: 20_design/architecture.json interfaces.exposed_surfaces
"""

from __future__ import annotations

import uuid

import psycopg2
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database import get_db
from app.models import AttachLabelRequest, ObjectLabelRecord, ObjectLabelsResponse
from app.service import LabelEngineError, LabelService

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


@router.post(
    "/objects/{object_id}/labels",
    response_model=ObjectLabelRecord,
    status_code=201,
)
def attach_label(object_id: str, body: AttachLabelRequest):
    """
    Attach a label to an object by name.
    Creates the label inline if it does not exist.
    Idempotent: duplicate attachment is silently ignored.

    Body must include object_type so the LabelEngine can scope grouped queries.
    """
    label_name = body.label_name.strip()
    if not label_name:
        return _api_error("LABEL_NAME_EMPTY", "Label name must not be empty.", status=422)

    object_type = body.object_type.strip()
    if not object_type:
        return _api_error("OBJECT_TYPE_REQUIRED", "object_type must not be empty.", status=422)

    try:
        with get_db() as conn:
            record = _svc.attach_label(conn, object_id, object_type, label_name)
    except LabelEngineError as exc:
        return _api_error(exc.code, exc.message, exc.status)
    except psycopg2.errors.CheckViolation:
        return _api_error(
            "OBJECT_TYPE_INVALID",
            "object_type must be lowercase (e.g. 'task', not 'Task').",
            status=422,
        )

    return record


@router.delete("/objects/{object_id}/labels/{label_id}", status_code=204)
def remove_label(object_id: str, label_id: str):
    """
    Remove a label from an object.
    Returns 404 ATTACHMENT_NOT_FOUND if the pair does not exist.
    Returns 404 LABEL_NOT_FOUND if the label does not exist.
    """
    try:
        with get_db() as conn:
            _svc.remove_label(conn, object_id, label_id)
    except LabelEngineError as exc:
        return _api_error(exc.code, exc.message, exc.status)


@router.get("/objects/{object_id}/labels", response_model=ObjectLabelsResponse)
def get_object_labels(object_id: str) -> ObjectLabelsResponse:
    """Return all labels attached to object_id, ordered by attached_at ASC."""
    with get_db() as conn:
        labels = _svc.get_labels_for_object(conn, object_id)
    return ObjectLabelsResponse(labels=labels)
