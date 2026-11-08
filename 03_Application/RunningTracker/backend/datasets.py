"""Dataset builders implementing the row shapes declared in 10_architecture.json exposed_surfaces."""

from datetime import datetime
from typing import Any, Optional

from fastapi.responses import JSONResponse

from platform_contracts import ColumnSchema, Dataset, DatasetMeta


def _col(key: str, label: str, type_: str, sortable: bool = True) -> ColumnSchema:
    return ColumnSchema(key=key, label=label, type=type_, sortable=sortable)


RUN_SCHEMA = [
    _col("started_at", "Date", "date"),
    _col("distance_m", "Distance (m)", "number"),
    _col("elapsed_s", "Duration (s)", "number"),
    _col("moving_s", "Moving (s)", "number"),
    _col("avg_pace_s_per_km", "Avg pace (s/km)", "number"),
    _col("avg_hr", "Avg HR", "number"),
    _col("max_hr", "Max HR", "number"),
    _col("sync_state", "Sync", "enum"),
    _col("status", "Status", "enum"),
    _col("run_type", "Type", "enum"),
    _col("finished_at", "Finished", "date"),
    _col("category", "Category", "string"),
    _col("route_id", "Route id", "string", sortable=False),
    _col("route_name", "Route", "string"),
    _col("comment", "Comment", "string", sortable=False),
    _col("device_name", "Device", "string"),
    _col("location_count", "GPS samples", "number"),
    _col("hr_count", "HR samples", "number"),
]
SPLIT_SCHEMA = [
    _col("km", "Km", "number"),
    _col("distance_m", "Distance (m)", "number"),
    _col("duration_s", "Time (s)", "number"),
    _col("pace_s_per_km", "Pace (s/km)", "number"),
    _col("avg_hr", "Avg HR", "number"),
    _col("partial", "Partial", "boolean"),
]
SERIES_SCHEMA = [
    _col("t_s", "Time (s)", "number"),
    # Chart x axis: LineChart sorts x as strings, so the label is a fixed-width h:mm:ss (sorts correctly).
    _col("t_label", "Time", "string"),
    _col("value", "Value", "number"),
]
PREPARED_SCHEMA = [
    _col("short_id", "Code", "string"),
    _col("title", "Title", "string"),
    _col("planned_for", "Planned", "date"),
    _col("expires_at", "Expires", "date"),
    _col("is_expired", "Expired", "boolean"),
    _col("created_at", "Created", "date"),
    _col("route_name", "Route", "string"),
    _col("ghost_label", "Ghost", "string"),
]
DEVICE_SCHEMA = [
    _col("name", "Name", "string"),
    _col("created_at", "Paired", "date"),
    _col("last_used_at", "Last used", "date"),
    _col("revoked_at", "Revoked", "date"),
    _col("is_revoked", "Revoked", "boolean"),
]
CODE_SCHEMA = [
    _col("code", "Code", "string", sortable=False),
    _col("expires_at", "Expires", "date"),
    _col("native_base_url", "Server", "string"),
]


def _dataset(object_type: str, label: str, schema: list[ColumnSchema], rows: list[dict[str, Any]],
             total: Optional[int] = None, page: int = 1, page_size: Optional[int] = None,
             row_actions: Optional[list[str]] = None) -> Dataset:
    return Dataset(
        meta=DatasetMeta(
            object_type=object_type, label=label,
            total=len(rows) if total is None else total,
            page=page, page_size=len(rows) if page_size is None else page_size,
            row_actions=row_actions or [],
        ),
        **{"schema": schema},
        rows=rows,
    )


def ds_response(dataset: Dataset, status: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status, content=dataset.model_dump(by_alias=True, mode="json"))


def run_row(r: dict) -> dict:
    """RunRow from a joined runs row (id, status, ..., device_name, avg_hr, max_hr, location_count, hr_count)."""
    distance, moving = r.get("distance_m"), r.get("moving_s")
    pace = moving / (distance / 1000.0) if distance and moving is not None else None
    return {
        "id": str(r["id"]),
        "run_type": r["run_type"],
        "status": r["status"],
        "sync_state": {"prepared": "prepared", "uploading": "pending", "complete": "synced"}[r["status"]],
        "started_at": r["started_at"], "finished_at": r["finished_at"],
        "elapsed_s": r["elapsed_s"], "moving_s": moving, "distance_m": distance,
        "avg_pace_s_per_km": pace,
        "avg_hr": r.get("avg_hr"), "max_hr": r.get("max_hr"),
        "category": r.get("category"), "route_id": str(r["route_id"]) if r.get("route_id") else None,
        "route_name": r.get("route_name"), "comment": r["comment"], "device_name": r.get("device_name"),
        "location_count": r.get("location_count") or 0, "hr_count": r.get("hr_count") or 0,
    }


def runs_dataset(rows: list[dict], total: int, page: int, page_size: int) -> Dataset:
    return _dataset("run", "Runs", RUN_SCHEMA, [run_row(r) for r in rows], total, page, page_size, ["delete"])


def splits_dataset(splits: list[dict]) -> Dataset:
    rows = [{"id": str(s["km"]), **s} for s in sorted(splits, key=lambda s: s["km"])]
    return _dataset("run_split", "Splits", SPLIT_SCHEMA, rows)


def _label(t_s: float) -> str:
    t = int(t_s)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def series_dataset(metric: str, points: list[list[float]]) -> Dataset:
    rows = [{"id": str(i), "t_s": p[0], "t_label": _label(p[0]), "value": p[1]}
            for i, p in enumerate(sorted(points, key=lambda p: p[0]))]
    return _dataset("run_series", "Pace" if metric == "pace" else "Heart rate", SERIES_SCHEMA, rows)


def _ghost_label(r: dict) -> Optional[str]:
    if not r.get("ghost_run_id"):
        return None
    when = r["ghost_started_at"].strftime("%Y-%m-%d") if r.get("ghost_started_at") else "?"
    t = r.get("ghost_moving_s")
    time = f"{int(t) // 60}:{int(t) % 60:02d}" if t is not None else "?"
    return f"{when} · {time}" + (f" · {r['ghost_category']}" if r.get("ghost_category") else "")


def prepared_dataset(rows: list[dict]) -> Dataset:
    out = [{
        "id": str(r["id"]), "short_id": r["short_id"], "title": r["title"], "planned_for": r["planned_for"],
        "expires_at": r["expires_at"], "is_expired": bool(r["is_expired"]), "created_at": r["created_at"],
        "route_name": r.get("route_name"), "ghost_label": _ghost_label(r),
    } for r in rows]
    return _dataset("prepared_run", "Prepared runs", PREPARED_SCHEMA, out, row_actions=["delete"])


def devices_dataset(rows: list[dict]) -> Dataset:
    out = [{
        "id": str(r["id"]), "name": r["name"], "created_at": r["created_at"],
        "last_used_at": r["last_used_at"], "revoked_at": r["revoked_at"], "is_revoked": r["revoked_at"] is not None,
    } for r in rows]
    return _dataset("device", "Devices", DEVICE_SCHEMA, out, row_actions=["revoke"])


def pairing_code_dataset(code_id: str, code: str, expires_at: datetime, native_base_url: Optional[str]) -> Dataset:
    row = {"id": code_id, "code": code, "expires_at": expires_at, "native_base_url": native_base_url}
    return _dataset("pairing_code", "Pairing code", CODE_SCHEMA, [row])


ROUTE_SCHEMA = [
    _col("name", "Name", "string"),
    _col("description", "Description", "string", sortable=False),
    _col("reference_distance_m", "Distance (m)", "number"),
    _col("is_loop", "Loop", "boolean"),
    _col("run_count", "Runs", "number"),
    _col("latest_run_at", "Latest run", "date"),
    _col("best_moving_s", "Best time (s)", "number"),
    _col("created_at", "Created", "date"),
]


def route_row(r: dict) -> dict:
    return {
        "id": str(r["id"]), "name": r["name"], "description": r["description"],
        "reference_distance_m": r["reference_distance_m"], "is_loop": r["is_loop"],
        "run_count": r.get("run_count") or 0, "latest_run_at": r.get("latest_run_at"),
        "best_moving_s": r.get("best_moving_s"), "created_at": r["created_at"],
    }


def routes_dataset(rows: list[dict]) -> Dataset:
    return _dataset("route", "Routes", ROUTE_SCHEMA, [route_row(r) for r in rows], row_actions=["delete"])


ROUTE_RUN_SCHEMA = [
    _col("started_at", "Date", "date"),
    _col("moving_s", "Moving (s)", "number"),
    _col("distance_m", "Distance (m)", "number"),
    _col("run_type", "Type", "enum"),
    _col("category", "Category", "string"),
    _col("avg_hr", "Avg HR", "number"),
    _col("ghost_eligible", "Ghost eligible", "boolean"),
    _col("ghost_reason", "Reason", "string"),
    _col("is_latest", "Latest eligible", "boolean"),
    _col("is_fastest", "Fastest eligible", "boolean"),
]


def route_runs_dataset(rows: list[dict]) -> Dataset:
    return _dataset("route_run", "Route runs", ROUTE_RUN_SCHEMA, rows)


def empty_dataset(object_type: str, label: str) -> Dataset:
    return _dataset(object_type, label, [], [], total=0, page=1, page_size=0)
