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


def find_ingredient(name: str, unit: str) -> dict[str, Any] | None:
    """Stock item for an ingredient: name case-insensitive, unit equal (or item has no unit)."""
    for it in list_items(kind="ingredient"):
        if it["name"].strip().lower() == name.strip().lower() and (it.get("unit") in (None, unit)):
            return it
    return None


def ensure_ingredient(name: str, unit: str) -> dict[str, Any]:
    it = find_ingredient(name, unit)
    if it:
        return it
    with _client() as c:
        body = {"name": name, "item_type": "consumable", "quantity": 0, "unit": unit,
                "source_tags": ["kitchen"]}
        return _check(c.post("/items", json=body))["rows"][0]


def find_batches(recipe_id: str, only_available: bool = True) -> list[dict[str, Any]]:
    rows = [i for i in list_items(kind="batch") if i.get("recipe_ref") == recipe_id]
    if only_available:
        rows = [i for i in rows if (i["quantity"] or 0) > 0]
    return sorted(rows, key=lambda i: i["created_at"])


def find_batch_for_meal(meal_id: str) -> dict[str, Any] | None:
    rows = list_items(kind="batch", source_tag=f"meal:{meal_id}")
    return rows[0] if rows else None


def create_batch(name: str, recipe_id: str, unit: str, location: str | None,
                 expires_at: str | None, meal_id: str) -> dict[str, Any]:
    with _client() as c:
        body = {"name": name, "item_type": "consumable", "kind": "batch", "quantity": 0,
                "unit": unit, "location": location, "expires_at": expires_at,
                "recipe_ref": recipe_id, "source_tags": ["kitchen", f"meal:{meal_id}"]}
        return _check(c.post("/items", json=body))["rows"][0]


def post_movement(item_id: str, delta: float, reason: str, key: str, ref: str | None = None) -> dict[str, Any]:
    with _client() as c:
        return _check(c.post(f"/items/{item_id}/movements",
                             json={"delta": delta, "reason": reason, "idempotency_key": key, "ref": ref}))


def reverse_movement(movement_id: str) -> dict[str, Any] | None:
    with _client() as c:
        r = c.post(f"/movements/{movement_id}/reverse")
        if r.status_code == 409:  # already reversed
            return None
        return _check(r)
