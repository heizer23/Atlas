"""
PreferenceStore — Pydantic request and response models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PutPreferenceRequest(BaseModel):
    """Request body for PUT /preferences/{scope}/{key}.

    'value' may be any valid JSON value including null.
    Using Optional[Any] with default=None would make the field optional,
    which is wrong — the field is required but may carry a null value.
    We use model_config to allow arbitrary types and accept null explicitly.
    """

    value: Any  # required; null is a valid value

    model_config = {"arbitrary_types_allowed": True}


class PreferenceRecord(BaseModel):
    """Response model for PUT and the row shape within Dataset rows for GET endpoints."""

    scope: str
    key: str
    value: Any
    updated_at: datetime
