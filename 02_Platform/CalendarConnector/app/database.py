"""
Postgres connection pool management and schema initialisation.

Reads DB connection string from environment (DATABASE_URL or ATLAS_PG_* vars).
Runs migrations/001_init.sql on startup via init_schema().

Note: init_schema() is the authoritative schema deployment path for this component.
The global migrate.py only scans Application paths; extension to Platform paths is
deferred to a future infrastructure sprint (see architecture.json design_decisions).
"""
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool

log = logging.getLogger("calendar_connector")

_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"

_pool: psycopg2.pool.SimpleConnectionPool | None = None


def _build_url() -> str:
    """Accept DATABASE_URL directly, or build it from ATLAS_PG_* vars."""
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


def init_pool() -> None:
    """Initialise the module-level psycopg2 connection pool from environment variables."""
    global _pool
    _pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=_build_url(),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


@contextmanager
def get_db() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a database connection from the pool; return it on exit."""
    assert _pool is not None, "Connection pool not initialised — call init_pool() first"
    conn = _pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def init_schema() -> None:
    """Execute migrations/001_init.sql to ensure all tables exist (idempotent)."""
    sql_path = _MIGRATIONS_DIR / "001_init.sql"
    sql = sql_path.read_text(encoding="utf-8")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    log.info("Schema initialised from %s", sql_path)
