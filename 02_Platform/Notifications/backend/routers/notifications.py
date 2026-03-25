"""
FastAPI router for notification lifecycle HTTP endpoints.

Endpoints:
  POST   /api/notifications/             — create a notification
  DELETE /api/notifications/{id}         — cancel a notification
  POST   /api/notifications/{id}/replace — replace a notification

All error responses use api_error() from platform_errorhandling.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.models import NotificationCreateRequest, NotificationRecord
from backend.service import NotificationNotFoundError, NotificationService
from platform_errorhandling.api_response import api_error

log = logging.getLogger("notifications.router")
router = APIRouter()
_service = NotificationService()


@router.post("/notifications/", response_model=NotificationRecord, status_code=201)
def create_notification(body: NotificationCreateRequest) -> NotificationRecord:
    """Persist notification with status=pending, return record with generated id."""
    return _service.create(body)


@router.delete("/notifications/{notification_id}")
def cancel_notification(notification_id: str) -> JSONResponse:
    """Cancel a pending notification by id.

    Returns 200 for pending->cancelled transition.
    Returns 200 (no-op) for already-dispatched, already-cancelled, or failed records.
    Returns 404 if the notification id does not exist.
    """
    try:
        _service.cancel(notification_id)
        return JSONResponse(status_code=200, content={"cancelled": notification_id})
    except NotificationNotFoundError:
        return api_error(
            code="NOTIFICATION_NOT_FOUND",
            message=f"Notification not found: {notification_id}",
            detail={"notification_id": notification_id},
            status=404,
        )


@router.post("/notifications/{notification_id}/replace", response_model=NotificationRecord, status_code=201)
def replace_notification(
    notification_id: str,
    body: NotificationCreateRequest,
) -> NotificationRecord:
    """Cancel old notification and create a new one.

    Returns new NotificationRecord with a new UUID on success.
    Returns 404 if old_id does not exist (new record is not created).
    This operation is not atomic — see architecture.json contracts.invariants.
    """
    try:
        return _service.replace(notification_id, body)
    except NotificationNotFoundError:
        return api_error(
            code="NOTIFICATION_NOT_FOUND",
            message=f"Notification not found: {notification_id}",
            detail={"notification_id": notification_id},
            status=404,
        )
