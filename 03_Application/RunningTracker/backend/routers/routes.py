"""Web routes: route library (list, detail, create from a completed run, edit, delete)."""

import uuid
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from psycopg2.extras import Json
from psycopg2.errors import UniqueViolation

from backend.config import ROUTE_GEOMETRY_VERSION
from backend.database import get_db
from backend.datasets import empty_dataset, ds_response, route_runs_dataset, routes_dataset
from backend.metrics import SampleRow
from backend.models import RouteCreate, RoutePatch
from backend.progress_store import recompute_progress
from backend.route_geometry import build_geometry
from platform_errorhandling import api_error

router = APIRouter(prefix="/routes", tags=["routes"])

# Best time = lowest moving time over complete runs on the route (any run type: a ghost is any run on the route).
ROUTE_SELECT = """
    select rt.id, rt.name, rt.description, rt.reference_distance_m, rt.is_loop, rt.created_at,
           count(r.id) filter (where r.status = 'complete') as run_count,
           max(r.started_at) filter (where r.status = 'complete') as latest_run_at,
           min(r.moving_s) filter (where r.status = 'complete') as best_moving_s
    from runningtracker.routes rt
    left join runningtracker.runs r on r.route_id = rt.id
"""
ROUTE_GROUP = " group by rt.id"


def _uuid(value: str) -> Optional[str]:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def _not_found(what: str = "Route") -> JSONResponse:
    return api_error("NOT_FOUND", f"{what} not found.", status=404)


def _name_taken() -> JSONResponse:
    return api_error("ROUTE_NAME_TAKEN", "A route with this name already exists.", status=409)


def _fetch(conn, route_id: str) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute(ROUTE_SELECT + " where rt.id = %s" + ROUTE_GROUP, (route_id,))
        return cur.fetchone()


@router.get("", response_model=None)
def list_routes() -> JSONResponse:
    """All routes, name A-Z (case-insensitive), no paging (a personal library). Empty library -> empty Dataset."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(ROUTE_SELECT + ROUTE_GROUP + " order by lower(rt.name), rt.id")
            rows = cur.fetchall()
    return ds_response(routes_dataset(rows))


@router.get("/{route_id}", response_model=None)
def get_route(route_id: str) -> JSONResponse:
    rid = _uuid(route_id)
    with get_db() as conn:
        row = _fetch(conn, rid) if rid else None
    return ds_response(routes_dataset([row])) if row else _not_found()


@router.get("/{route_id}/runs", response_model=None)
def route_runs(route_id: str) -> JSONResponse:
    """Completed runs on the route, newest first, with ghost eligibility (any run type qualifies if it covered the
    route) and the latest/fastest eligible markers used for ghost selection. Fastest = lowest moving_s."""
    rid = _uuid(route_id)
    with get_db() as conn:
        if rid is None or _fetch(conn, rid) is None:
            return _not_found()
        with conn.cursor() as cur:
            cur.execute(
                """
                select r.id, r.started_at, r.moving_s, r.distance_m, r.run_type, r.category, m.avg_hr,
                       coalesce(p.qualified, false) as ghost_eligible, p.reason as ghost_reason
                from runningtracker.runs r
                left join runningtracker.run_metrics m on m.run_id = r.id
                left join runningtracker.run_route_progress p on p.run_id = r.id
                where r.route_id = %s and r.status = 'complete'
                order by r.started_at desc, r.id
                """,
                (rid,),
            )
            rows = cur.fetchall()
    eligible = [r for r in rows if r["ghost_eligible"]]
    latest = eligible[0]["id"] if eligible else None
    fastest = min(eligible, key=lambda r: (r["moving_s"] is None, r["moving_s"]))["id"] if eligible else None
    out = [{**r, "id": str(r["id"]), "ghost_reason": r["ghost_reason"] or (None if r["ghost_eligible"] else "no_progress_data"),
            "is_latest": r["id"] == latest, "is_fastest": r["id"] == fastest} for r in rows]
    return ds_response(route_runs_dataset(out))


@router.post("", response_model=None)
def create_route(body: RouteCreate) -> JSONResponse:
    """Create a route from a completed run's location samples and link that run to it."""
    run_id = _uuid(body.run_id)
    name = body.name.strip()
    if not name:
        return api_error("VALIDATION_ERROR", "Route name must not be blank.", status=422)
    with get_db() as conn:
        with conn.cursor() as cur:
            run = None
            if run_id:
                cur.execute("select status from runningtracker.runs where id = %s for update", (run_id,))
                run = cur.fetchone()
            if run is None:
                return _not_found("Run")
            if run["status"] != "complete":
                return api_error("RUN_NOT_COMPLETE", "A route can only be created from a completed run.", status=409)
            cur.execute("select seq, sample_ts, payload from runningtracker.run_samples "
                        "where run_id = %s and stream = 'location' order by seq", (run_id,))
            geo = build_geometry([SampleRow(r["seq"], r["sample_ts"], r["payload"]) for r in cur.fetchall()])
            if geo is None:
                return api_error("ROUTE_GEOMETRY_UNAVAILABLE", "The run has too little usable GPS data for a route.", status=422)
            description = (body.description or "").strip() or None
            try:
                cur.execute(
                    """
                    insert into runningtracker.routes
                        (name, description, geometry, reference_distance_m, is_loop, point_count, geometry_version, source_run_id)
                    values (%s, %s, %s, %s, %s, %s, %s, %s) returning id
                    """,
                    (name, description, Json(geo["geometry"]), geo["reference_distance_m"], geo["is_loop"],
                     geo["point_count"], ROUTE_GEOMETRY_VERSION, run_id),
                )
            except UniqueViolation:
                conn.rollback()
                return _name_taken()
            route_id = str(cur.fetchone()["id"])
            cur.execute("update runningtracker.runs set route_id = %s, updated_at = now() where id = %s", (route_id, run_id))
        recompute_progress(conn, run_id)
        conn.commit()
        row = _fetch(conn, route_id)
    return ds_response(routes_dataset([row]), status=201)


@router.patch("/{route_id}", response_model=None)
def patch_route(route_id: str, body: RoutePatch) -> JSONResponse:
    """name: omitted = unchanged (null is rejected); description: omitted = unchanged, null/blank = cleared."""
    rid = _uuid(route_id)
    with get_db() as conn:
        if rid is None or _fetch(conn, rid) is None:
            return _not_found()
        fields = body.model_fields_set
        if "name" in fields and (body.name is None or not body.name.strip()):
            return api_error("VALIDATION_ERROR", "Route name must not be blank.", status=422)
        try:
            with conn.cursor() as cur:
                if "name" in fields:
                    cur.execute("update runningtracker.routes set name = %s, updated_at = now() where id = %s",
                                (body.name.strip(), rid))
                if "description" in fields:
                    desc = body.description.strip() if body.description is not None else None
                    cur.execute("update runningtracker.routes set description = %s, updated_at = now() where id = %s",
                                (desc or None, rid))
        except UniqueViolation:
            conn.rollback()
            return _name_taken()
        conn.commit()
        row = _fetch(conn, rid)
    return ds_response(routes_dataset([row]))


@router.delete("/{route_id}", response_model=None)
def delete_route(route_id: str) -> JSONResponse:
    """Refused while any run references the route: historical ghost comparisons must not silently lose their reference."""
    rid = _uuid(route_id)
    with get_db() as conn:
        if rid is None or _fetch(conn, rid) is None:
            return _not_found()
        with conn.cursor() as cur:
            cur.execute("select count(*) as n from runningtracker.runs where route_id = %s", (rid,))
            if cur.fetchone()["n"]:
                return api_error("ROUTE_IN_USE", "Unlink the runs from this route before deleting it.", status=409)
            cur.execute("delete from runningtracker.routes where id = %s", (rid,))
        conn.commit()
    return ds_response(empty_dataset("route", "Routes"))
