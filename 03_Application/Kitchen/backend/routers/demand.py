"""Demand sync status / retry (Kitchen -> StorageTracker central shopping list)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend import demand_sync
from backend.common import dataset_response

router = APIRouter(prefix="/kitchen", tags=["demand"])


@router.get("/demand/status", response_model=None)
def demand_status() -> JSONResponse:
    """status: pending (never synced) | ok | error. `problems` = per-line reasons of a rejected snapshot,
    `issues` = planning flags (draft recipes, excluded lines, missing bases). On error StorageTracker still holds
    the last accepted snapshot."""
    return dataset_response("demand_sync", [demand_sync.get_status()], "Demand sync")


@router.post("/demand/sync", response_model=None)
def demand_sync_now() -> JSONResponse:
    """Retry: recompute from the current plan and publish. Idempotent, safe to repeat."""
    return dataset_response("demand_sync", [demand_sync.sync_demand()], "Demand sync")
