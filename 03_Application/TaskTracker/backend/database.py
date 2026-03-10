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
    """Run schema DDL on startup — idempotent (uses IF NOT EXISTS)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                create schema if not exists tasktracker;

                create table if not exists tasktracker.tasks (
                    id          uuid        primary key default gen_random_uuid(),
                    title       text        not null,
                    description text,
                    status      text        not null default 'open'
                                            check (status in ('open', 'in_progress', 'done')),
                    priority    text        not null default 'medium'
                                            check (priority in ('low', 'medium', 'high')),
                    due_date    date,
                    created_at  timestamptz not null default now(),
                    updated_at  timestamptz not null default now()
                );

                create index if not exists ix_tasks_status
                    on tasktracker.tasks(status);

                create index if not exists ix_tasks_created_at
                    on tasktracker.tasks(created_at desc);
            """)
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
