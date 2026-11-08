"""Web routes: history list, detail, splits, series, comment patch, delete."""

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.database import get_db
from backend.datasets import (
    ds_response, empty_dataset, runs_dataset, series_dataset, splits_dataset,
)
from backend.models import RunPatch
from backend.progress_store import recompute_progress
from platform_contracts import Dataset
from platform_errorhandling import api_error

router = APIRouter(prefix="/runs", tags=["runs"])

RUN_SELECT = """
    select r.id, r.run_type, r.status, r.started_at, r.finished_at, r.elapsed_s, r.moving_s, r.distance_m,
           r.comment, r.category, r.route_id, rt.name as route_name, d.name as device_name, m.avg_hr, m.max_hr,
           (select count(*) from runningtracker.run_samples s where s.run_id = r.id and s.stream = 'location') as location_count,
           (select count(*) from runningtracker.run_samples s where s.run_id = r.id and s.stream = 'heart_rate') as hr_count
    from runningtracker.runs r
    left join runningtracker.devices d on d.id = r.device_id
    left join runningtracker.run_metrics m on m.run_id = r.id
    left join runningtracker.routes rt on rt.id = r.route_id
"""


def _uuid(value: str) -> Optional[str]:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def _not_found() -> JSONResponse:
    return api_error("NOT_FOUND", "Run not found.", status=404)


def _fetch_run(conn, run_id: str) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute(RUN_SELECT + " where r.id = %s", (run_id,))
        return cur.fetchone()


def _single(row: dict) -> Dataset:
    return runs_dataset([row], total=1, page=1, page_size=1)


@router.get("", response_model=None)
def list_runs(
    status: Optional[Literal["prepared", "uploading", "complete"]] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> JSONResponse:
    if status is None:
        where, params, order = "r.status in ('uploading', 'complete')", [], "r.started_at desc nulls last, r.id asc"
    else:
        where, params = "r.status = %s", [status]
        order = "r.created_at desc, r.id asc" if status == "prepared" else "r.started_at desc nulls last, r.id asc"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) as n from runningtracker.runs r where {where}", params)
            total = cur.fetchone()["n"]
            cur.execute(RUN_SELECT + f" where {where} order by {order} limit %s offset %s",
                        params + [page_size, (page - 1) * page_size])
            rows = cur.fetchall()
    return ds_response(runs_dataset(rows, total, page, page_size))


@router.get("/{run_id}", response_model=None)
def get_run(run_id: str) -> JSONResponse:
    rid = _uuid(run_id)
    with get_db() as conn:
        row = _fetch_run(conn, rid) if rid else None
    if row is None:
        return _not_found()
    return ds_response(_single(row))


def _metrics_column(run_id: str, column: str):
    """(run exists, column value or None) for one run_metrics JSON column."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from runningtracker.runs where id = %s", (run_id,))
            if cur.fetchone() is None:
                return False, None
            cur.execute(f"select {column} as v from runningtracker.run_metrics where run_id = %s", (run_id,))
            row = cur.fetchone()
    return True, (row["v"] if row else None)


@router.get("/{run_id}/splits", response_model=None)
def get_splits(run_id: str) -> JSONResponse:
    rid = _uuid(run_id)
    exists, splits = _metrics_column(rid, "splits") if rid else (False, None)
    if not exists:
        return _not_found()
    return ds_response(splits_dataset(splits or []))


@router.get("/{run_id}/series", response_model=None)
def get_series(run_id: str, metric: Literal["pace", "heart_rate"]) -> JSONResponse:
    rid = _uuid(run_id)
    column = "pace_series" if metric == "pace" else "hr_series"
    exists, points = _metrics_column(rid, column) if rid else (False, None)
    if not exists:
        return _not_found()
    return ds_response(series_dataset(metric, points or []))


@router.patch("/{run_id}", response_model=None)
def patch_run(run_id: str, body: RunPatch) -> JSONResponse:
    """Comment/category edit (U1): omitted = unchanged; null or blank = NULL; string = trimmed."""
    rid = _uuid(run_id)
    with get_db() as conn:
        if rid is None or _fetch_run(conn, rid) is None:
            return _not_found()
        if "category" in body.model_fields_set:
            category = body.category.strip() if body.category is not None else None
            with conn.cursor() as cur:
                cur.execute("update runningtracker.runs set category = %s, updated_at = now() where id = %s",
                            (category or None, rid))
        if "route_id" in body.model_fields_set:
            new_route = None
            if body.route_id is not None:
                new_route = _uuid(body.route_id)
                found = None
                if new_route:
                    with conn.cursor() as cur:
                        cur.execute("select 1 from runningtracker.routes where id = %s", (new_route,))
                        found = cur.fetchone()
                if found is None:
                    return api_error("NOT_FOUND", "Route not found.", status=404)
            with conn.cursor() as cur:
                cur.execute("update runningtracker.runs set route_id = %s, updated_at = now() where id = %s", (new_route, rid))
            recompute_progress(conn, rid)
        if "comment" in body.model_fields_set:
            comment = body.comment.strip() if body.comment is not None else None
            with conn.cursor() as cur:
                cur.execute("update runningtracker.runs set comment = %s, updated_at = now() where id = %s",
                            (comment or None, rid))
        conn.commit()
        row = _fetch_run(conn, rid)
    return ds_response(_single(row))


@router.delete("/{run_id}", response_model=None)
def delete_run(run_id: str) -> JSONResponse:
    rid = _uuid(run_id)
    deleted = None
    if rid:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from runningtracker.runs where id = %s returning id", (rid,))
                deleted = cur.fetchone()
            conn.commit()
    if deleted is None:
        return _not_found()
    return ds_response(empty_dataset("run", "Runs"))
