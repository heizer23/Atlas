"""Thin HTTP client for StorageTracker, the single source of truth for stock.

Kitchen never touches the storagetracker schema directly; everything goes
through the public /api contract (items + stock movements).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

BASE_URL = os.environ.get("STORAGETRACKER_URL", "http://atlas-storagetracker:8000").rstrip("/")


class StorageError(RuntimeError):
    pass


def _client() -> httpx.Client:
    return httpx.Client(base_url=f"{BASE_URL}/api", timeout=10.0)


def _check(r: httpx.Response) -> Any:
    if r.status_code >= 400:
        raise StorageError(f"StorageTracker {r.request.method} {r.request.url.path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def list_items(**params: str) -> list[dict[str, Any]]:
    with _client() as c:
        return _check(c.get("/items", params=params))["rows"]


def get_item(item_id: int) -> dict[str, Any] | None:
    with _client() as c:
        r = c.get(f"/items/{item_id}")
        if r.status_code == 404:
            return None
        return _check(r)["rows"][0]


def find_ingredient(name: str, unit: str) -> dict[str, Any] | None:
    """Legacy lookup by name (case-insensitive) + unit; only used to migrate pre-1.1 recipes to article ids."""
    for it in list_items(kind="ingredient"):
        if it["name"].strip().lower() == name.strip().lower() and (it.get("unit") in (None, unit)):
            return it
    return None


def create_ingredient(name: str, unit: str) -> dict[str, Any]:
    """New article (stock 0). Callers must have the user's explicit confirmation."""
    with _client() as c:
        body = {"name": name, "item_type": "consumable", "quantity": 0, "unit": unit, "source_tags": ["kitchen"]}
        return _check(c.post("/items", json=body))["rows"][0]


FRIDGE = "Fridge"
FREEZER = "Freezer"


def storage_of(batch: dict[str, Any]) -> str:
    """'freezer' if the batch location is the freezer, else 'fridge' (ready to use; also legacy/blank locations)."""
    return "freezer" if (batch.get("location") or "").strip().lower() == FREEZER.lower() else "fridge"


def location_label(storage: str) -> str:
    return FREEZER if storage == "freezer" else FRIDGE


def is_expired(batch: dict[str, Any], today: str) -> bool:
    """expires_at is the last good day (ISO strings compare chronologically)."""
    return bool(batch.get("expires_at")) and batch["expires_at"] < today


def find_batches(recipe_id: str, only_available: bool = True, include_expired: bool = False,
                 storage: str | None = "fridge") -> list[dict[str, Any]]:
    """Batches of a base recipe, earliest expiry first (no date last), then oldest.
    Default = ready to use: in the fridge and not expired. storage=None returns fridge + freezer;
    storage='freezer' only frozen. Expired batches are excluded unless include_expired: they must be
    confirmed/discarded, never auto-consumed. Archived (depleted) batches are never returned."""
    from backend.common import berlin_today
    today = berlin_today().isoformat()
    rows = [i for i in list_items(kind="batch") if i.get("recipe_ref") == recipe_id]
    if only_available:
        rows = [i for i in rows if (i["quantity"] or 0) > 0]
    if storage:
        rows = [i for i in rows if storage_of(i) == storage]
    if not include_expired:
        rows = [i for i in rows if not is_expired(i, today)]
    return sorted(rows, key=lambda i: (i.get("expires_at") or "9999-12-31", i["created_at"]))


def find_batches_for_meal(meal_id: str) -> list[dict[str, Any]]:
    """All batches (also archived) produced by one cooking; used to make a repeated cook confirmation safe."""
    return list_items(kind="batch", source_tag=f"meal:{meal_id}", archived="include")


def create_batch(name: str, recipe_id: str, unit: str, location: str, expires_at: str | None,
                 produced_at: str, meal_id: str, alloc: str) -> dict[str, Any]:
    with _client() as c:
        body = {"name": name, "item_type": "consumable", "kind": "batch", "quantity": 0,
                "unit": unit, "location": location, "expires_at": expires_at, "produced_at": produced_at,
                "recipe_ref": recipe_id, "source_tags": ["kitchen", f"meal:{meal_id}", f"alloc:{alloc}"]}
        return _check(c.post("/items", json=body))["rows"][0]


def update_item(item_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    with _client() as c:
        return _check(c.patch(f"/items/{item_id}", json=patch))["rows"][0]


def relocate(item_id: int, location: str, event: str, expires_at: str | None) -> dict[str, Any]:
    """freeze / thaw / move with an explicit best-before date (StorageTracker rejects freeze/thaw without one)."""
    with _client() as c:
        return _check(c.post(f"/items/{item_id}/relocate",
                             json={"location": location, "event": event, "expires_at": expires_at}))["rows"][0]


def post_movement(item_id: int, delta: float, reason: str, key: str, ref: str | None = None) -> dict[str, Any]:
    with _client() as c:
        return _check(c.post(f"/items/{item_id}/movements",
                             json={"delta": delta, "reason": reason, "idempotency_key": key, "ref": ref}))


def reverse_movement(movement_id: str) -> dict[str, Any] | None:
    with _client() as c:
        r = c.post(f"/movements/{movement_id}/reverse")
        if r.status_code == 409:  # already reversed
            return None
        return _check(r)
