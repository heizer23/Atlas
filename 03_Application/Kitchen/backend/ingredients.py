"""Ingredient identity: StorageTracker items are the article master; Kitchen stores their ids.

Line status (see line_status):
  base           line references a base recipe (batch inventory), no article needed
  matched        item_id exists in the master and the unit is compatible
  unit_mismatch  item_id exists but the recipe unit differs from the article's base unit (never converted)
  unknown_id     item_id not found in the master (rejected on save)
  unresolved     no item_id yet
A recipe is 'active' only if every line is base or matched; otherwise 'draft'.
"""

from __future__ import annotations

from typing import Any

from backend import storage_client as st


def master_items() -> list[dict[str, Any]]:
    """Raw ingredients only: consumable items of kind 'ingredient' (batches excluded). Zero stock included."""
    return [i for i in st.list_items(kind="ingredient") if i.get("item_type") == "consumable"]


def master_by_id() -> dict[int, dict[str, Any]]:
    return {i["id"]: i for i in master_items()}


def norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def units_compatible(line_unit: str, item_unit: str | None) -> bool:
    """Same base unit (case-insensitive). An article without base unit accepts the recipe's unit."""
    return item_unit is None or norm(line_unit) == norm(item_unit)


def line_status(line: dict[str, Any], master: dict[int, dict[str, Any]]) -> str:
    if line.get("base_recipe_id"):
        return "base"
    item_id = line.get("item_id")
    if not item_id:
        return "unresolved"
    item = master.get(int(item_id))
    if item is None:
        return "unknown_id"
    return "matched" if units_compatible(line["unit"], item.get("unit")) else "unit_mismatch"


def recipe_status(lines: list[dict[str, Any]], master: dict[int, dict[str, Any]]) -> str:
    return "active" if lines and all(line_status(l, master) in ("base", "matched") for l in lines) else "draft"


def suggestions(name: str, master_list: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Plain lookup aid, no fuzzy/AI matching: exact name first, then substring either way."""
    n = norm(name)
    exact = [i for i in master_list if norm(i["name"]) == n]
    partial = [i for i in master_list if i not in exact and n and (n in norm(i["name"]) or norm(i["name"]) in n)]
    return [{"id": i["id"], "name": i["name"], "unit": i.get("unit")} for i in (exact + partial)[:limit]]
