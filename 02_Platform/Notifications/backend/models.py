"""
Pydantic request and response models for the Notifications platform API.

INVARIANT: NotificationRecord must never include fcm_token.
fcm_token is accepted in NotificationCreateRequest but is a platform-internal
dispatch field — it must never appear in API responses.

INVARIANT: ImmediateSendResponse must never include fcm_token.
"""

from datetime import datetime

from pydantic import BaseModel, field_validator


class NotificationCreateRequest(BaseModel):
    source:     str
    fire_at:    datetime
    title:      str
    body:       str
    label:      str
    deep_link:  str
    fcm_token:  str

    @field_validator("deep_link")
    @classmethod
    def deep_link_must_use_atlas_scheme(cls, v: str) -> str:
        if not v.startswith("atlas://"):
            raise ValueError("deep_link must begin with atlas://")
        return v


class NotificationRecord(BaseModel):
    """API response shape for a notification. fcm_token is intentionally absent."""
    id:         str
    source:     str
    fire_at:    datetime
    title:      str
    body:       str
    label:      str
    deep_link:  str
    status:     str
    created_at: datetime


class ImmediateSendRequest(BaseModel):
    """Request body for POST /api/notifications/send.

    Caller provides only title and body. FCM token is resolved internally
    from the default device registration. source is optional audit metadata.
    """
    title:  str
    body:   str
    source: str = "claude"


class ImmediateSendResponse(BaseModel):
    """Response for a successful immediate send.

    dispatched_at is server time captured after FCM send() returned successfully.
    fcm_token is intentionally absent.
    """
    id:            str
    title:         str
    body:          str
    dispatched_at: datetime
