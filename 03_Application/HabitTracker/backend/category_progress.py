"""
Category progress: the single place that turns "which habits are done" into a daily level.

Level of a category on a day = highest priority among its *done* habits (0 if none, None if
the category has no habit active that day). Completion criteria stay with the habit itself
(entry / threshold / linked source); priority only ranks it. Many small habits never add up
to a bigger level.

Derived on read, by date — nothing is stored, so history stays consistent when a priority or
category is edited later (levels reflect the current mapping; see CLAUDE.md).

Discipline: only habits with an explicit done signal (a logged tap / confirmed review result)
count. "Done" here is never inferred from the absence of a negative event, so an untouched
day is level 0 ("nothing confirmed"), not success. `_discipline_level` is the extension point
for a later rule (e.g. completion across several behavioural goals).
"""

from __future__ import annotations

from typing import Iterable, Mapping


def _highest_level(habits: Iterable[Mapping]) -> int:
    return max((h["priority"] for h in habits if h["done"] and h["priority"]), default=0)


def _discipline_level(habits: Iterable[Mapping]) -> int:
    return _highest_level(habits)


_LEVEL_BY_KIND = {"achievement": _highest_level, "discipline": _discipline_level}


def category_levels(categories: Iterable[Mapping], habits: Iterable[Mapping]) -> dict[str, int | None]:
    """categories: {id, kind}. habits: {category_id, priority, done} — only habits ACTIVE that day.
    Returns {category_id: level | None}. Uncategorised habits (category_id None) are ignored."""
    by_cat: dict[str, list[Mapping]] = {}
    for h in habits:
        if h["category_id"] is not None:
            by_cat.setdefault(str(h["category_id"]), []).append(h)
    out: dict[str, int | None] = {}
    for c in categories:
        cid = str(c["id"])
        members = by_cat.get(cid)
        out[cid] = _LEVEL_BY_KIND.get(c["kind"], _highest_level)(members) if members else None
    return out
