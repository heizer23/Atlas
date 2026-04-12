"""
Chronos NumericSeries skill — thin adapter for batch measurement submission.

Responsibilities:
- Map human label/alias inputs to catalog keys via case-insensitive match
- Construct a batch request: {recorded_at, measurements: [{key, value}]}
- Call POST /api/measurements/batch on the NumericSeries backend
- Fail explicitly on unmapped or ambiguous labels (no silent remapping)

This skill does NOT contain business logic. It is a pure mapping + HTTP adapter.

Architecture: Sprint03_Chronos&UXpt2/10_architecture.json §internal_flow[8] (chronos_skill)

Configuration:
  NUMERIC_SERIES_URL: base URL of the NumericSeries backend (e.g. http://atlas-numeric-series:8000)
  Defaults to http://localhost:8014 for local development.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import requests


# ── Exceptions ─────────────────────────────────────────────────────────────────

class ChronosUnmappedError(Exception):
    """Raised when a label does not match any catalog entry."""
    def __init__(self, label: str) -> None:
        super().__init__(f"Label '{label}' does not match any known measurement definition.")
        self.label = label


class ChronosAmbiguousError(Exception):
    """Raised when a label matches multiple catalog entries."""
    def __init__(self, label: str, matches: list[str]) -> None:
        super().__init__(
            f"Label '{label}' is ambiguous — matches keys: {', '.join(matches)}. "
            "Provide a more specific label."
        )
        self.label = label
        self.matches = matches


# ── Catalog loading ────────────────────────────────────────────────────────────

def load_catalog() -> list[dict]:
    """
    Fetch measurement definitions from GET /api/measurement-definitions.
    Returns the rows list from the Dataset response.
    Raises requests.HTTPError or requests.ConnectionError on failure.
    """
    base_url = os.environ.get("NUMERIC_SERIES_URL", "http://localhost:8014")
    url = f"{base_url.rstrip('/')}/api/measurement-definitions"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("rows", [])


# ── Key resolution ─────────────────────────────────────────────────────────────

def _resolve_key(label: str, catalog: list[dict]) -> str:
    """
    Case-insensitive exact match of label against each catalog entry's
    key, label, and aliases fields.

    Returns the matched catalog key.
    Raises ChronosUnmappedError if no match.
    Raises ChronosAmbiguousError if multiple matches (defensive — should not
    happen with a well-defined catalog).
    """
    label_lower = label.strip().lower()
    matched_keys: list[str] = []

    for entry in catalog:
        candidates = [
            entry.get("key", ""),
            entry.get("label", ""),
        ] + [str(a) for a in entry.get("aliases", [])]

        if any(c.lower() == label_lower for c in candidates if c):
            matched_keys.append(entry["key"])

    if len(matched_keys) == 0:
        raise ChronosUnmappedError(label)
    if len(matched_keys) > 1:
        raise ChronosAmbiguousError(label, matched_keys)
    return matched_keys[0]


# ── Main entry point ───────────────────────────────────────────────────────────

def submit_measurements(
    measurements: list[dict],
    recorded_at: str | None = None,
) -> dict:
    """
    Submit measurements to NumericSeries via the batch endpoint.

    Args:
        measurements: list of {label: str, value: float/int}
        recorded_at: optional ISO-8601 timestamp. Defaults to current UTC time.

    Returns:
        dict — the parsed JSON response from POST /api/measurements/batch
               on success: {inserted: int}

    Raises:
        ChronosUnmappedError: if any label does not match a catalog entry
        ChronosAmbiguousError: if any label matches multiple catalog entries
        requests.HTTPError: if the batch API returns an HTTP error
        requests.ConnectionError: if the backend is unreachable
    """
    if recorded_at is None:
        recorded_at = datetime.now(tz=timezone.utc).isoformat()

    # Load catalog
    catalog = load_catalog()

    # Resolve all labels to keys — fail fast on first unmapped/ambiguous
    resolved: list[dict] = []
    for item in measurements:
        label = item.get("label", "")
        value = item["value"]
        key = _resolve_key(label, catalog)  # raises on failure
        resolved.append({"key": key, "value": value})

    # Construct and send batch request
    base_url = os.environ.get("NUMERIC_SERIES_URL", "http://localhost:8014")
    url = f"{base_url.rstrip('/')}/api/measurements/batch"

    payload = {
        "recorded_at": recorded_at,
        "measurements": resolved,
    }

    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()
