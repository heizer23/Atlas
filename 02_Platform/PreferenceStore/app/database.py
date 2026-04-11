"""
PreferenceStore — database connection pool and schema initialization.

Owns the 'preferences' schema in the shared Postgres instance.
Pattern: identical to LabelEngine.
"""

import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool


def _build_url() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    return "postgresql://{user}:{password}@{host}:{port}/{db}".format(
        user     = os.environ.get("ATLAS_PG_USER",     "atlas"),
        password = os.environ.get("ATLAS_PG_PASSWORD", ""),
        host     = os.environ.get("ATLAS_PG_HOST",     "127.0.0.1"),
        port     = os.environ.get("ATLAS_PG_PORT",     "5432"),
        db       = os.environ.get("ATLAS_PG_DB",       "atlas"),
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
    """Create preferences schema and table idempotently."""
    ddl = """
        create schema if not exists preferences;

        create table if not exists preferences.preferences (
            scope       text        not null,
            key         text        not null,
            value_json  jsonb       not null,
            updated_at  timestamptz not null default now(),
            constraint preferences_pkey primary key (scope, key),
            constraint preferences_scope_nonempty check (length(trim(scope)) > 0),
            constraint preferences_key_nonempty   check (length(trim(key))   > 0)
        );

        create index if not exists ix_preferences_scope
            on preferences.preferences (scope);
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
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
