"""Web routes: prepared runs, pairing codes, devices."""

import os
import uuid
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.config import PREPARED_RUN_TTL_HOURS, SHORT_ID_LENGTH
from backend.database import get_db
from backend.datasets import (
    devices_dataset, ds_response, pairing_code_dataset, prepared_dataset,
)
from backend.models import PreparedRunCreate
from backend.progress_store import resolve_ghost
from backend.pairing import create_pairing_code, new_code, revoke_device
from platform_errorhandling import api_error

router = APIRouter(tags=["pairing"])

PREPARED_SELECT = """
    select r.id, r.short_id, r.title, r.planned_for, r.expires_at, (now() > r.expires_at) as is_expired, r.created_at,
           r.route_id, rt.name as route_name, r.ghost_run_id,
           g.started_at as ghost_started_at, g.moving_s as ghost_moving_s, g.category as ghost_category
    from runningtracker.runs r
    left join runningtracker.routes rt on rt.id = r.route_id
    left join runningtracker.runs g on g.id = r.ghost_run_id
    where r.status = 'prepared'
"""


def _uuid(value: str) -> Optional[str]:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


@router.get("/prepared-runs", response_model=None)
def list_prepared_runs() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(PREPARED_SELECT + " order by r.created_at desc")
            rows = cur.fetchall()
    return ds_response(prepared_dataset(rows))


@router.post("/prepared-runs", status_code=201, response_model=None)
def create_prepared_run(body: PreparedRunCreate = PreparedRunCreate()) -> JSONResponse:
    title = (body.title or "").strip() or None
    route_id = None
    if body.route_id is not None:
        route_id = _uuid(body.route_id)
    if body.ghost != "none" and body.route_id is None:
        return api_error("VALIDATION_ERROR", "A ghost needs a route.", status=422)
    with get_db() as conn:
        ghost_id = None
        if body.route_id is not None:
            found = None
            if route_id:
                with conn.cursor() as cur:
                    cur.execute("select 1 from runningtracker.routes where id = %s", (route_id,))
                    found = cur.fetchone()
            if found is None:
                return api_error("NOT_FOUND", "Route not found.", status=404)
            selector = body.ghost if body.ghost in ("none", "latest", "fastest") else (_uuid(body.ghost) or "")
            if selector == "":
                return api_error("VALIDATION_ERROR", "ghost must be none, latest, fastest or a run id.", status=422)
            try:
                ghost_id = resolve_ghost(conn, route_id, selector)
            except ValueError:
                return api_error("GHOST_NOT_ELIGIBLE", "No eligible ghost run on this route.", status=409)
        with conn.cursor() as cur:
            for _ in range(10):  # retry on short_id collision
                cur.execute(
                    """
                    insert into runningtracker.runs (id, status, short_id, title, planned_for, expires_at, route_id, ghost_run_id)
                    values (%s, 'prepared', %s, %s, %s, now() + make_interval(hours => %s), %s, %s)
                    on conflict do nothing
                    returning id
                    """,
                    (str(uuid.uuid4()), new_code(SHORT_ID_LENGTH), title, body.planned_for, PREPARED_RUN_TTL_HOURS, route_id, ghost_id),
                )
                created = cur.fetchone()
                if created:
                    break
            else:
                return api_error("INTERNAL_ERROR", "Could not allocate a short id.", status=500)
            cur.execute(PREPARED_SELECT + " and r.id = %s", (created["id"],))
            row = cur.fetchone()
        conn.commit()
    return ds_response(prepared_dataset([row]), status=201)


@router.post("/pairing-codes", status_code=201, response_model=None)
def create_code() -> JSONResponse:
    with get_db() as conn:
        code_id, code, expires_at = create_pairing_code(conn)
    base_url = os.environ.get("RUNNINGTRACKER_NATIVE_BASE_URL") or None
    return ds_response(pairing_code_dataset(code_id, code, expires_at, base_url), status=201)


@router.get("/devices", response_model=None)
def list_devices() -> JSONResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select id, name, created_at, last_used_at, revoked_at from runningtracker.devices order by created_at desc")
            rows = cur.fetchall()
    return ds_response(devices_dataset(rows))


@router.post("/devices/{device_id}/revoke", response_model=None)
def revoke(device_id: str) -> JSONResponse:
    did = _uuid(device_id)
    row = None
    if did:
        with get_db() as conn:
            row = revoke_device(conn, did)
    if row is None:
        return api_error("NOT_FOUND", "Device not found.", status=404)
    return ds_response(devices_dataset([row]))
