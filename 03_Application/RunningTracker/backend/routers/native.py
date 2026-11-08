"""Native routes under /native: machine-to-machine (AtlasPhone), tailnet only, exempt from Dataset.

Router-level dependency native_guard; every route except pair also depends on require_device.
Failures use the platform ApiError envelope (AppError -> main.py handler).
"""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.config import ALGO_VERSION
from backend.database import get_db
from backend.metrics import recompute_and_store
from backend.models import (
    BeginRequest, BeginResponse, FinishRequest, FinishResponse, PairRequest, PairResponse,
    PreparedRunList, PreparedRunOut, SamplesBatch, SamplesResponse, parse_sample_ts,
)
from backend.progress_store import recompute_progress
from backend.pairing import PairingFailed, PairingRateLimited, redeem_pairing_code
from backend.security import AppError, DeviceContext, native_guard, require_device
from backend.verification import read_cursors, verify_run

router = APIRouter(prefix="/native", tags=["native"], dependencies=[Depends(native_guard)])


def _run_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise AppError("NOT_FOUND", "Run not found.", 404)


def _not_found() -> AppError:
    return AppError("NOT_FOUND", "Run not found.", 404)


@router.post("/pair", response_model=PairResponse)
def pair(body: PairRequest):
    with get_db() as conn:
        try:
            return redeem_pairing_code(conn, body.code, body.device_name)
        except PairingRateLimited:
            raise AppError("PAIRING_RATE_LIMITED", "Too many attempts. Create a new code and try again later.", 429)
        except PairingFailed:
            raise AppError("PAIRING_FAILED", "Pairing failed.", 403)


PREPARED_NATIVE_SELECT = """
    select id, short_id, run_type, title, planned_for, expires_at, route_id, ghost_run_id
    from runningtracker.runs
    where status = 'prepared' and expires_at > now()
"""


def _prepared_out(r: dict) -> PreparedRunOut:
    return PreparedRunOut(
        id=str(r["id"]), short_id=r["short_id"], run_type=r["run_type"], title=r["title"],
        planned_for=r["planned_for"], expires_at=r["expires_at"],
        route_id=str(r["route_id"]) if r["route_id"] else None,
        ghost_run_id=str(r["ghost_run_id"]) if r["ghost_run_id"] else None,
    )


@router.get("/prepared-runs", response_model=PreparedRunList)
def native_list_prepared(device: DeviceContext = Depends(require_device)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(PREPARED_NATIVE_SELECT + " order by created_at desc")
            return PreparedRunList(prepared_runs=[_prepared_out(r) for r in cur.fetchall()])


@router.get("/prepared-runs/{run_id}", response_model=PreparedRunOut)
def native_get_prepared(run_id: str, device: DeviceContext = Depends(require_device)):
    rid = _run_id(run_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(PREPARED_NATIVE_SELECT + " and id = %s", (rid,))
            row = cur.fetchone()
    if row is None:
        raise _not_found()
    return _prepared_out(row)


def _begin_response(conn, run_id: str, status: str) -> BeginResponse:
    highs, contiguous = read_cursors(conn, run_id)
    return BeginResponse(run_id=run_id, status=status, high_seq=highs, contiguous_seq=contiguous)


@router.post("/runs/{run_id}/begin", response_model=BeginResponse)
def begin(run_id: str, body: BeginRequest, device: DeviceContext = Depends(require_device)):
    rid = _run_id(run_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select r.id, r.status, r.device_id, (d.revoked_at is not null) as owner_revoked
                from runningtracker.runs r left join runningtracker.devices d on d.id = r.device_id
                where r.id = %s for update of r
                """,
                (rid,),
            )
            run = cur.fetchone()
            if run is None:
                # unknown id -> new uploading run owned by the caller (conflict = concurrent begin, re-read below)
                cur.execute(
                    """
                    insert into runningtracker.runs (id, run_type, status, started_at, device_id)
                    values (%s, %s, 'uploading', %s, %s)
                    on conflict (id) do nothing
                    """,
                    (rid, body.run_type, body.started_at, device.device_id),
                )
                status = "uploading"
                if cur.rowcount == 0:
                    cur.execute("select status, device_id from runningtracker.runs where id = %s", (rid,))
                    row = cur.fetchone()
                    if str(row["device_id"]) != device.device_id:
                        raise _not_found()
                    status = row["status"]
            elif run["status"] == "prepared":
                cur.execute(
                    """
                    update runningtracker.runs
                    set status = 'uploading', started_at = %s, device_id = %s, updated_at = now()
                    where id = %s
                    """,
                    (body.started_at, device.device_id, rid),
                )
                status = "uploading"
            elif str(run["device_id"]) == device.device_id:
                status = run["status"]
            elif run["owner_revoked"] and run["status"] != "complete":
                cur.execute(
                    "update runningtracker.runs set device_id = %s, updated_at = now() where id = %s",
                    (device.device_id, rid),
                )
                status = run["status"]
            else:
                raise _not_found()
        response = _begin_response(conn, rid, status)
        conn.commit()
    return response


def _owned_run(cur, run_id: str, device: DeviceContext) -> dict:
    """The run row if the caller owns it; 404 otherwise; 409 for a prepared run that was never begun."""
    cur.execute("select id, status, device_id, started_at from runningtracker.runs where id = %s for update", (run_id,))
    run = cur.fetchone()
    if run is None:
        raise _not_found()
    if run["status"] == "prepared":
        raise AppError("RUN_NOT_STARTED", "Run has not been started yet. Call begin first.", 409)
    if str(run["device_id"]) != device.device_id:
        raise _not_found()
    return run


@router.put("/runs/{run_id}/samples", response_model=SamplesResponse)
def put_samples(run_id: str, body: SamplesBatch, device: DeviceContext = Depends(require_device)):
    rid = _run_id(run_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            run = _owned_run(cur, rid, device)
            if run["status"] != "uploading":
                raise AppError("RUN_NOT_UPLOADABLE", "Run is already complete.", 409)
            # One atomic statement: existing rows are never modified (duplicates ignored).
            cur.execute(
                """
                insert into runningtracker.run_samples (run_id, stream, seq, sample_ts, payload)
                select %s, t.stream, t.seq, t.ts, t.payload::jsonb
                from unnest(%s::text[], %s::bigint[], %s::timestamptz[], %s::text[]) as t(stream, seq, ts, payload)
                on conflict (run_id, stream, seq) do nothing
                """,
                (
                    rid,
                    [s.stream for s in body.samples],
                    [s.seq for s in body.samples],
                    [parse_sample_ts(s.payload) for s in body.samples],
                    [json.dumps(s.payload) for s in body.samples],
                ),
            )
            stored = cur.rowcount
        highs, contiguous = read_cursors(conn, rid)
        conn.commit()
    return SamplesResponse(stored=stored, duplicates=len(body.samples) - stored, high_seq=highs, contiguous_seq=contiguous)


@router.post("/runs/{run_id}/finish", response_model=FinishResponse)
def finish(run_id: str, body: FinishRequest, device: DeviceContext = Depends(require_device)):
    rid = _run_id(run_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            run = _owned_run(cur, rid, device)
            if body.finished_at < run["started_at"]:
                raise AppError("VALIDATION_ERROR", "finished_at must not be before started_at.", 422)

            if run["status"] == "complete":
                # Idempotent: same answer; recompute only when the algorithm version changed.
                cur.execute("select algo_version from runningtracker.run_metrics where run_id = %s", (rid,))
                metrics = cur.fetchone()
                result = verify_run(conn, rid, body.expected_counts, body.last_seq)
                if result.result == "complete" and (metrics is None or metrics["algo_version"] != ALGO_VERSION):
                    recompute_and_store(conn, rid)
                conn.commit()
                return result

            cur.execute(
                """
                update runningtracker.runs
                set finished_at = %s, elapsed_s = %s, moving_s = %s, distance_m = %s, updated_at = now()
                where id = %s
                """,
                (body.finished_at, body.elapsed_s, body.moving_s, body.distance_m, rid),
            )
            # Pauses are replaced as a set on every finish call (idempotent).
            cur.execute("delete from runningtracker.run_pauses where run_id = %s", (rid,))
            for p in {p.started_at: p for p in body.pauses}.values():
                cur.execute(
                    """
                    insert into runningtracker.run_pauses (run_id, started_at, ended_at, started_elapsed_s, ended_elapsed_s)
                    values (%s, %s, %s, %s, %s)
                    """,
                    (rid, p.started_at, p.ended_at, p.started_elapsed_s, p.ended_elapsed_s),
                )
        result = verify_run(conn, rid, body.expected_counts, body.last_seq)
        if result.result == "complete":
            recompute_and_store(conn, rid)
            with conn.cursor() as cur:
                cur.execute("update runningtracker.runs set status = 'complete', updated_at = now() where id = %s", (rid,))
            recompute_progress(conn, rid)
        conn.commit()
    return result


@router.get("/routes/{route_id}")
def native_get_route(route_id: str, device: DeviceContext = Depends(require_device)):
    """Reference geometry for offline use: [[lat, lon, cumulative_m], ...]. Immutable per geometry_version."""
    try:
        rid = str(uuid.UUID(route_id))
    except ValueError:
        raise AppError("NOT_FOUND", "Route not found.", 404)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, name, geometry_version, reference_distance_m, is_loop, geometry "
                "from runningtracker.routes where id = %s", (rid,))
            row = cur.fetchone()
    if row is None:
        raise AppError("NOT_FOUND", "Route not found.", 404)
    return {"route_id": str(row["id"]), "name": row["name"], "geometry_version": row["geometry_version"],
            "reference_distance_m": row["reference_distance_m"], "is_loop": row["is_loop"], "geometry": row["geometry"]}


@router.get("/runs/{run_id}/ghost-profile")
def native_get_ghost_profile(run_id: str, device: DeviceContext = Depends(require_device)):
    """Ghost profile of a completed run on its route: points [moving_t_s, progress_m, hr_bpm|null]. 404 unless qualified."""
    rid = _run_id(run_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select route_id, geometry_version, algo_version, end_progress_m, profile "
                "from runningtracker.run_route_progress where run_id = %s and qualified", (rid,))
            row = cur.fetchone()
    if row is None:
        raise AppError("NOT_FOUND", "No ghost profile for this run.", 404)
    points = row["profile"]
    return {"run_id": rid, "route_id": str(row["route_id"]), "geometry_version": row["geometry_version"],
            "algo_version": row["algo_version"], "time_basis": "moving_seconds",
            "end_progress_m": row["end_progress_m"], "duration_s": points[-1][0], "points": points}
