"""
Postgres connection pool for the Notifications platform service.

Follows the same pattern as WorkoutTracker/backend/database.py and
TaskTracker/backend/database.py. Called once on FastAPI startup via init_pool().
"""

import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool


def _build_url() -> str:
    """Accept DATABASE_URL directly, or build it from ATLAS_PG_* vars."""
    if url := os.environ.get("DATABASE_URL"):
        return url
    return (
        "postgresql://{user}:{password}@{host}:{port}/{db}".format(
            user     = os.environ.get("ATLAS_PG_USER",     "atlas"),
            password = os.environ.get("ATLAS_PG_PASSWORD", ""),
            host     = os.environ.get("ATLAS_PG_HOST",     "127.0.0.1"),
            port     = os.environ.get("ATLAS_PG_PORT",     "5432"),
            db       = os.environ.get("ATLAS_PG_DB",       "atlas"),
        )
    )


_pool: psycopg2.pool.SimpleConnectionPool | None = None


def init_pool() -> None:
    """Initialise the module-level psycopg2 connection pool from DATABASE_URL env var.
    Called once on FastAPI startup.
    """
    global _pool
    _pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=_build_url(),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


@contextmanager
def get_db() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager that yields a connection from the pool and returns it on exit.
    Used by service and dispatch job.
    """
    assert _pool is not None, "Connection pool not initialised — call init_pool() first"
    conn = _pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
