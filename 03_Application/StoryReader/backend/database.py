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


DATABASE_URL = _build_url()

_pool: psycopg2.pool.SimpleConnectionPool | None = None


def init_pool() -> None:
    global _pool
    _pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def init_schema() -> None:
    """Run schema DDL on startup — idempotent (uses IF NOT EXISTS).

    Executes schema.sql as the single canonical source of truth.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        ddl = f.read()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)


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
