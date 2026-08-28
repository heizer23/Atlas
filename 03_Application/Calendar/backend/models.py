"""
Calendar — Pydantic request/response models.

CalendarEventCreate: POST body — all required fields plus optional nullables.
CalendarEventPatch: PATCH body — all fields Optional; uses UNSET sentinel to
  distinguish "field not provided" from "field provided as explicit null".
"""
from typing import Any
from pydantic import BaseModel

# Sentinel distinguishing omission from explicit None in PATCH bodies.
# Usage: if field is UNSET → skip in SQL SET clause.
#         if field is None → set to NULL.
#         if field has a value → set to that value.
_UNSET_SENTINEL = object()
UNSET: Any = _UNSET_SENTINEL


# Valid enum values — enforced at application layer (schema has DB CHECK too)
VALID_EVENT_TYPES = {"task_block", "personal_block", "blocker"}
VALID_SOURCE_TYPES = {"task"}


class CalendarEventCreate(BaseModel):
    title: str
    start_at: str                          # ISO-8601 datetime string
    end_at: str                            # ISO-8601 datetime string
    event_type: str                        # task_block | personal_block | blocker
    source_object_type: str | None = None  # task | null
    source_object_id: str | None = None    # task UUID or null
    notes: str | None = None


class CalendarEventPatch(BaseModel):
    """
    PATCH body. All fields are Optional with default UNSET.
    - Omitted field → UNSET → not included in SQL UPDATE
    - Provided as None → None → SET field = NULL (for nullable fields)
    - Provided with value → included in SQL UPDATE with that value
    """
    title: Any = UNSET
    start_at: Any = UNSET
    end_at: Any = UNSET
    event_type: Any = UNSET
    source_object_type: Any = UNSET
    source_object_id: Any = UNSET
    notes: Any = UNSET
