"""Batch lifecycle events: relocate (move / freeze / thaw) and archive.

Contract (Kitchen batch management):
- relocate changes `location` and records an event row in item_history: `freeze` / `thaw` / `location_change`
  with old -> new location, plus an `expiry_change` row when the best-before date changes.
- Freezing and thawing never reset shelf life implicitly: `expires_at` is REQUIRED (explicit date, not in the past)
  for event freeze/thaw. The caller (Kitchen) derives it from a configured policy and shows it to the user.
- archive removes a depleted item (quantity 0) from active inventory; history and the row stay.
  Batches are archived/unarchived automatically by stock movements (see movements._apply).
"""
from datetime import date

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db
from backend.routers.items import (
    _record_history, _row_to_dict, _single_item_dataset, _dataset_response, berlin_today,
)
from platform_errorhandling import api_error

router = APIRouter(prefix="/items", tags=["batches"])

EVENTS = {"move", "freeze", "thaw"}
COLS = """id, name, item_type, state, location, notes, source_tags,
          quantity, min_quantity, restock_quantity, unit, expires_at, kind, recipe_ref,
          produced_at, archived_at, created_at, updated_at"""


class RelocateIn(BaseModel):
    location:   str
    event:      str = "move"
    expires_at: date | None = None


@router.post("/{item_id}/relocate", response_model=None)
def relocate(item_id: int, body: RelocateIn) -> JSONResponse:
    if body.event not in EVENTS:
        return api_error("VALIDATION_ERROR", f"event must be one of: {', '.join(sorted(EVENTS))}")
    if not body.location.strip():
        return api_error("VALIDATION_ERROR", "location must not be empty")
    if body.event in ("freeze", "thaw"):
        if body.expires_at is None:
            return api_error("VALIDATION_ERROR",
                             f"expires_at is required for {body.event}: shelf life is never reset implicitly")
        if body.expires_at < berlin_today():
            return api_error("VALIDATION_ERROR", "expires_at must not be in the past")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"select {COLS} from storagetracker.items where id = %s for update", (item_id,))
            cur_row = cur.fetchone()
            if not cur_row:
                return api_error("NOT_FOUND", f"Item {item_id} not found", status=404)
            if body.event in ("freeze", "thaw") and not (cur_row["quantity"] and cur_row["quantity"] > 0):
                return api_error("CONFLICT", f"Nothing to {body.event}: quantity is 0", status=409)
            old_loc, old_exp = cur_row["location"], cur_row["expires_at"]
            new_exp = body.expires_at if body.expires_at is not None else old_exp
            cur.execute(
                f"""update storagetracker.items set location = %s, expires_at = %s, updated_at = now()
                    where id = %s returning {COLS}""",
                (body.location.strip(), new_exp, item_id),
            )
            row = cur.fetchone()
        history_type = body.event if body.event != "move" else "location_change"
        _record_history(conn, item_id, history_type, old_loc, body.location.strip(),
                        notes=f"best-before {old_exp or '-'} -> {new_exp or '-'}" if body.event != "move" else None)
        if new_exp != old_exp:
            _record_history(conn, item_id, "expiry_change", str(old_exp) if old_exp else None,
                            str(new_exp) if new_exp else None, notes=body.event)
        conn.commit()
    return _dataset_response(_single_item_dataset(_row_to_dict(row)))


@router.post("/{item_id}/archive", response_model=None)
def archive(item_id: int) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select quantity from storagetracker.items where id = %s for update", (item_id,))
            r = cur.fetchone()
            if not r:
                return api_error("NOT_FOUND", f"Item {item_id} not found", status=404)
            if r["quantity"] and r["quantity"] > 0:
                return api_error("CONFLICT", "Only depleted items (quantity 0) can be archived", status=409)
            cur.execute(f"update storagetracker.items set archived_at = coalesce(archived_at, now()) "
                        f"where id = %s returning {COLS}", (item_id,))
            row = cur.fetchone()
        conn.commit()
    return _dataset_response(_single_item_dataset(_row_to_dict(row)))


@router.post("/{item_id}/unarchive", response_model=None)
def unarchive(item_id: int) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"update storagetracker.items set archived_at = null where id = %s returning {COLS}", (item_id,))
            row = cur.fetchone()
            if not row:
                return api_error("NOT_FOUND", f"Item {item_id} not found", status=404)
        conn.commit()
    return _dataset_response(_single_item_dataset(_row_to_dict(row)))
