#!/usr/bin/env python3
"""
strip_sprint_markers.py

Strips sprint-context markers from a 10_architecture.json to produce a clean
00_architecture/architecture.json after sprint close.

Usage:
    python3 strip_sprint_markers.py <input_path> <output_path>

Marker rules:
  In string values (any array of strings):
    "[NEW] ..."     → keep, strip prefix
    "[CHANGED] ..." → keep, strip prefix
    "[REMOVED] ..." → remove entry entirely

  In interface endpoint objects:
    { "change": "new" | "changed", ... } → keep, remove "change" field
    { "change": "removed", ... }         → remove object entirely

  Top-level field:
    "sprint_note"   → remove field entirely
"""

import json
import sys
from pathlib import Path


STRIP_PREFIXES = ("[NEW] ", "[CHANGED] ")
REMOVE_PREFIX  = "[REMOVED] "


def clean_string_list(items: list) -> list:
    result = []
    for item in items:
        if not isinstance(item, str):
            result.append(item)
            continue
        if item.startswith(REMOVE_PREFIX):
            continue
        for prefix in STRIP_PREFIXES:
            if item.startswith(prefix):
                item = item[len(prefix):]
                break
        result.append(item)
    return result


def clean_endpoint_list(endpoints: list) -> list:
    result = []
    for ep in endpoints:
        if not isinstance(ep, dict):
            result.append(ep)
            continue
        change = ep.get("change", "")
        if change == "removed":
            continue
        ep = {k: v for k, v in ep.items() if k != "change"}
        result.append(ep)
    return result


def clean_value(key: str, value):
    """Recursively clean a value based on its key and type."""
    if isinstance(value, list) and value and all(isinstance(i, str) for i in value):
        return clean_string_list(value)
    if isinstance(value, list) and value and all(isinstance(i, dict) for i in value):
        # Any list of objects may carry "change" markers (endpoints, files, etc.)
        return clean_endpoint_list(value)
    if isinstance(value, dict):
        return clean_dict(value)
    if isinstance(value, list):
        return [clean_value("", item) if isinstance(item, dict) else item for item in value]
    return value


def clean_dict(d: dict) -> dict:
    result = {}
    for k, v in d.items():
        if k == "sprint_note":
            continue
        result[k] = clean_value(k, v)
    return result


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_path> <output_path>")
        sys.exit(1)

    input_path  = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    data = json.loads(input_path.read_text())
    cleaned = clean_dict(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False))
    print(f"Cleaned: {input_path} → {output_path}")


if __name__ == "__main__":
    main()
