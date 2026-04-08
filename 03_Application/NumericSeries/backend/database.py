"""
NumericSeries — database connection pool and schema init.

Source of truth: Sprint01/20_design/architecture.json persistence section.
Schema: Sprint01/20_Data/schema.sql
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool


def _build_url() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    return (
        "postgresql://{user}:{password}@{host}:{port}/{db}".format(
            user=os.environ.get("ATLAS_PG_USER", "atlas"),
            password=os.environ.get("ATLAS_PG_PASSWORD", ""),
            host=os.environ.get("ATLAS_PG_HOST", "127.0.0.1"),
            port=os.environ.get("ATLAS_PG_PORT", "5432"),
            db=os.environ.get("ATLAS_PG_DB", "atlas"),
        )
    )


_pool: psycopg2.pool.SimpleConnectionPool | None = None


def init_pool() -> None:
    global _pool
    _pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=_build_url(),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def init_schema() -> None:
    """Execute schema.sql — idempotent (all statements use IF NOT EXISTS)."""
    schema_path = Path(__file__).resolve().parents[2] / "Sprint01" / "20_Data" / "schema.sql"
    sql = schema_path.read_text()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


@contextmanager
def get_db() -> Generator[psycopg2.extensions.connection, None, None]:
    assert _pool is not None, "Connection pool not initialised — call init_pool() first"
    conn = _pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
