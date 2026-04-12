"""
NumericSeries — business logic service.

Sparkline derivation, latest_value selection, measurement validation, and
series read model assembly. No HTTP concerns.

Source of truth: Sprint01/20_design/scaffolding.json service.py
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import psycopg2.extensions


# Sparkline window: N most recent measurements
SPARKLINE_LIMIT = 20


class NumericSeriesError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class NumericSeriesService:

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_measurement(self, value: float, recorded_at: str) -> None:
        """
        Raise NumericSeriesError with INVALID_VALUE or INVALID_TIMESTAMP
        if the inputs are not valid.
        """
        if not math.isfinite(value):
            raise NumericSeriesError(
                "INVALID_VALUE",
                "Measurement value must be a finite number.",
                status=422,
            )
        try:
            datetime.fromisoformat(recorded_at)
        except (ValueError, TypeError):
            raise NumericSeriesError(
                "INVALID_TIMESTAMP",
                f"recorded_at must be a valid ISO-8601 timestamp, got: {recorded_at!r}",
                status=422,
            )

    # ── Individual series helpers ─────────────────────────────────────────────

    def get_sparkline_points(
        self,
        conn: psycopg2.extensions.connection,
        label_id: str,
        limit: int = SPARKLINE_LIMIT,
    ) -> list[dict]:
        """
        Return the N most recent measurements as [{v: float, ts: int}] ordered by
        recorded_at ASC. ts is Unix epoch milliseconds — enables time-proportional
        x-axis rendering on the frontend.

        Sprint03: replaces get_sparkline_values().
        Architecture: Sprint03/10_architecture.json §internal_flow[3] (sparkline_data)
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT value,
                       EXTRACT(EPOCH FROM recorded_at)::bigint * 1000 AS ts_ms
                FROM (
                    SELECT value, recorded_at
                    FROM numeric_series.measurements
                    WHERE label_id = %s
                    ORDER BY recorded_at DESC
                    LIMIT %s
                ) sub
                ORDER BY recorded_at ASC
                """,
                (label_id, limit),
            )
            rows = cur.fetchall()
        return [{"v": float(r["value"]), "ts": int(r["ts_ms"])} for r in rows]

    def get_series_stats(
        self,
        conn: psycopg2.extensions.connection,
        label_id: str,
    ) -> dict:
        """
        Return min and max values over ALL measurements for label_id.
        Returns {min_value: float|None, max_value: float|None}.

        Sprint03: supports 4-column list row layout.
        Architecture: Sprint03/10_architecture.json §internal_flow[3] (sparkline_data)
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT MIN(value) AS min_val, MAX(value) AS max_val
                FROM numeric_series.measurements
                WHERE label_id = %s
                """,
                (label_id,),
            )
            row = cur.fetchone()
        if not row or row["min_val"] is None:
            return {"min_value": None, "max_value": None}
        return {"min_value": float(row["min_val"]), "max_value": float(row["max_val"])}

    def get_latest_value(
        self,
        conn: psycopg2.extensions.connection,
        label_id: str,
    ) -> float | None:
        """
        Return the value of the measurement with the most recent recorded_at,
        or None if no measurements exist.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT value FROM numeric_series.measurements
                WHERE label_id = %s
                ORDER BY recorded_at DESC
                LIMIT 1
                """,
                (label_id,),
            )
            row = cur.fetchone()
        return float(row["value"]) if row else None

    # ── List read ─────────────────────────────────────────────────────────────

    def list_series_rows(
        self,
        conn: psycopg2.extensions.connection,
    ) -> list[dict]:
        """
        Return all series joined with label names, each augmented with
        latest_value and sparkline_values (JSON-encoded string), sorted by
        label name ascending.

        sparkline_values is serialized as a JSON string so it can be carried
        in a Dataset row as ColumnType 'string'. UI Implementer must parse it.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.label_id::text AS id,
                       l.name           AS label_name,
                       (
                           SELECT value
                           FROM numeric_series.measurements m
                           WHERE m.label_id = s.label_id
                           ORDER BY m.recorded_at DESC
                           LIMIT 1
                       ) AS latest_value
                FROM numeric_series.series s
                JOIN labels.labels l ON l.id = s.label_id
                ORDER BY l.name ASC
                """
            )
            rows = cur.fetchall()

        result = []
        for row in rows:
            sparkline_points = self.get_sparkline_points(conn, row["id"])
            stats = self.get_series_stats(conn, row["id"])
            result.append(
                {
                    "id": row["id"],
                    "label_name": row["label_name"],
                    "latest_value": float(row["latest_value"]) if row["latest_value"] is not None else None,
                    "sparkline_points": json.dumps(sparkline_points),
                    "min_value": stats["min_value"],
                    "max_value": stats["max_value"],
                }
            )
        return result

    # ── Detail read ───────────────────────────────────────────────────────────

    def get_measurement_history(
        self,
        conn: psycopg2.extensions.connection,
        label_id: str,
    ) -> list[dict]:
        """
        Return all measurements for label_id ordered by recorded_at DESC.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text,
                       label_id::text,
                       value,
                       recorded_at::text
                FROM numeric_series.measurements
                WHERE label_id = %s
                ORDER BY recorded_at DESC
                """,
                (label_id,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ── Batch read ────────────────────────────────────────────────────────────

    def assemble_batch(
        self,
        conn: psycopg2.extensions.connection,
        label_ids: list[str],
    ) -> list[dict]:
        """
        Query labels.labels unconditionally for all requested label_ids to
        obtain label_name. For each:
          - if a series record exists in numeric_series.series, return all measurements
          - otherwise return empty measurements array
        label_name is None for label_ids not found in labels.labels.
        """
        if not label_ids:
            return []

        # Fetch label names unconditionally from LabelEngine schema
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text, name FROM labels.labels WHERE id = ANY(%s)",
                (label_ids,),
            )
            label_rows = cur.fetchall()
        label_map = {r["id"]: r["name"] for r in label_rows}

        # Fetch measurements for all known series
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text,
                       label_id::text,
                       value,
                       recorded_at::text
                FROM numeric_series.measurements
                WHERE label_id = ANY(%s)
                ORDER BY label_id, recorded_at ASC
                """,
                (label_ids,),
            )
            meas_rows = cur.fetchall()

        # Group measurements by label_id
        meas_by_label: dict[str, list[dict]] = {lid: [] for lid in label_ids}
        for r in meas_rows:
            lid = r["label_id"]
            if lid in meas_by_label:
                meas_by_label[lid].append(
                    {
                        "id": r["id"],
                        "label_id": r["label_id"],
                        "value": float(r["value"]),
                        "recorded_at": r["recorded_at"],
                    }
                )

        return [
            {
                "label_id": lid,
                "label_name": label_map.get(lid),
                "measurements": meas_by_label[lid],
            }
            for lid in label_ids
        ]
