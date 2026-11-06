"""Stock-movement ledger.

Contract (Kitchen Sprint01):
- items.quantity is the cached sum of applied deltas (movements.delta).
- A movement never drives quantity below 0: delta is clamped, requested_delta keeps the ask.
- idempotency_key makes POST safe to repeat: the original movement is returned (200, replayed=true).
- reverse posts the negated applied delta; a movement can be reversed once.
- stock_management_type='KANBAN' items are never deducted: movements are recorded with delta 0.
- kind='batch' items skip the low-stock auto transition and shopping tasks.
"""
import json as _json
from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import get_db
from backend.routers.items import (
    SHOPPING_TRIGGER_STATES, _apply_auto_transition, _ensure_open_shopping_task,
    _num, _record_history,
)
from platform_errorhandling import api_error

router = APIRouter(tags=["movements"])

COLS = "id, item_id, delta, requested_delta, reason, ref, idempotency_key, reverses_id, created_at"


class MovementCreate(BaseModel):
    delta:           float
    reason:          str
    ref:             str | None = None
    idempotency_key: str | None = None


def _movement_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    for k in ("id", "reverses_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ("delta", "requested_delta"):
        d[k] = _num(d[k])
    d["created_at"] = d["created_at"].isoformat()
    return d


def _apply(conn: Any, item_id: int, delta: float, reason: str, ref: str | None,
           key: str | None, reverses_id: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Returns (movement, item_quantity_info, replayed). Caller commits."""
    with conn.cursor() as cur:
        cur.execute(
            "select id, state, kind, stock_management_type, quantity, min_quantity, source_tags "
            "from storagetracker.items where id = %s for update",
            (item_id,),
        )
        item = cur.fetchone()
        if not item:
            raise LookupError(f"Item {item_id} not found")

        if key:
            cur.execute(f"select {COLS} from storagetracker.stock_movements where idempotency_key = %s", (key,))
            existing = cur.fetchone()
            if existing:
                if existing["item_id"] != item_id:
                    raise ValueError("idempotency_key already used for a different item")
                return _movement_to_dict(existing), {"quantity": _num(item["quantity"] or 0)}, True

        old_q = Decimal(item["quantity"] or 0)
        requested = Decimal(str(delta))
        # KANBAN articles are never deducted: the movement is still recorded (idempotency, undo, audit) with delta 0
        # and requested_delta keeps the ask; the manual status in items.state stays untouched.
        kanban = item["stock_management_type"] == "KANBAN"
        applied = Decimal(0) if kanban else max(requested, -old_q)
        new_q = old_q + applied

        cur.execute(
            f"""
            insert into storagetracker.stock_movements
                (item_id, delta, requested_delta, reason, ref, idempotency_key, reverses_id)
            values (%s, %s, %s, %s, %s, %s, %s)
            returning {COLS}
            """,
            (item_id, applied, requested, reason, ref, key, reverses_id),
        )
        movement = _movement_to_dict(cur.fetchone())

        state = item["state"]
        if item["kind"] != "batch" and not kanban:
            auto = _apply_auto_transition(new_q, item["min_quantity"])
            if auto:
                state = auto
            elif state == "low_stock":
                state = "stored"
        # depleted batches leave active inventory (history stays); a reversal that restores stock reactivates them
        cur.execute(
            """
            update storagetracker.items
            set quantity = %s, state = %s, updated_at = now(),
                archived_at = case when kind = 'batch' and %s = 0 then coalesce(archived_at, now())
                                   when kind = 'batch' then null else archived_at end
            where id = %s
            """,
            (new_q, state, new_q, item_id),
        )
    if applied != 0:
        _record_history(conn, item_id, "quantity_change", str(_num(old_q)), str(_num(new_q)), notes=reason)
    if state != item["state"]:
        _record_history(conn, item_id, "state_change", item["state"], state)
    if state in SHOPPING_TRIGGER_STATES and item["kind"] != "batch" and not kanban:
        tags = item["source_tags"] or []
        _ensure_open_shopping_task(conn, item_id, tags if isinstance(tags, list) else _json.loads(tags))
    return movement, {"quantity": _num(new_q)}, False


def _response(movement: dict, info: dict, replayed: bool) -> JSONResponse:
    return JSONResponse(
        status_code=200 if replayed else 201,
        content={"movement": movement, "quantity": info["quantity"], "replayed": replayed},
    )


@router.post("/items/{item_id}/movements", response_model=None)
def create_movement(item_id: int, body: MovementCreate) -> JSONResponse:
    if not body.reason.strip():
        return api_error("VALIDATION_ERROR", "reason must not be empty")
    with get_db() as conn:
        try:
            result = _apply(conn, item_id, body.delta, body.reason.strip(), body.ref,
                            body.idempotency_key, None)
        except LookupError as e:
            return api_error("NOT_FOUND", str(e), status=404)
        except ValueError as e:
            return api_error("CONFLICT", str(e), status=409)
        conn.commit()
    return _response(*result)


@router.post("/movements/{movement_id}/reverse", response_model=None)
def reverse_movement(movement_id: str) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"select {COLS} from storagetracker.stock_movements where id = %s", (movement_id,))
            mv = cur.fetchone()
            if not mv:
                return api_error("NOT_FOUND", f"Movement {movement_id} not found", status=404)
            if mv["reverses_id"] is not None:
                return api_error("CONFLICT", "A reversal cannot be reversed", status=409)
            cur.execute("select id from storagetracker.stock_movements where reverses_id = %s", (movement_id,))
            if cur.fetchone():
                return api_error("CONFLICT", "Movement already reversed", status=409)
        result = _apply(conn, mv["item_id"], -float(mv["delta"]), f"reverse:{mv['reason']}",
                        mv["ref"], None, movement_id)
        conn.commit()
    return _response(*result)


@router.get("/items/{item_id}/movements", response_model=None)
def list_movements(item_id: int) -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select id from storagetracker.items where id = %s", (item_id,))
            if not cur.fetchone():
                return api_error("NOT_FOUND", f"Item {item_id} not found", status=404)
            cur.execute(
                f"select {COLS} from storagetracker.stock_movements where item_id = %s order by created_at desc",
                (item_id,),
            )
            rows = [_movement_to_dict(r) for r in cur.fetchall()]
    return JSONResponse(content={"rows": rows, "total": len(rows)})
