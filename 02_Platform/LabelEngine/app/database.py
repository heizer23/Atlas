"""
LabelEngine — database connection pool and schema initialization.

Owns the 'labels' schema in the shared Postgres instance.
Pattern: identical to LinkingEngine.
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
    """Create labels schema tables idempotently using schema.sql."""
    # schema.sql lives in the sprint folder alongside the app source tree
    schema_path = (
        Path(__file__).parent.parent
        / "Spint01- First labels"
        / "20_Data"
        / "schema.sql"
    )
    if schema_path.exists():
        ddl = schema_path.read_text()
    else:
        # Inline DDL fallback — kept in sync with 20_Data/schema.sql.
        # Used in deployments where the sprint folder is absent.
        ddl = _inline_ddl()

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()


def _inline_ddl() -> str:
    """Return inline DDL — kept in sync with 20_Data/schema.sql."""
    return """
        create schema if not exists labels;

        create table if not exists labels.labels (
            id         text        not null default gen_random_uuid()::text,
            name       text        not null,
            created_at timestamptz not null default now(),
            constraint labels_pkey primary key (id),
            constraint labels_name_nonempty check (length(trim(name)) > 0)
        );

        create index if not exists ix_labels_name_lower
            on labels.labels (lower(name));

        create table if not exists labels.object_labels (
            object_id   text        not null,
            label_id    text        not null references labels.labels(id),
            object_type text        not null,
            attached_at timestamptz not null default now(),
            constraint object_labels_pkey primary key (object_id, label_id),
            constraint object_labels_object_type_lowercase check (object_type = lower(object_type))
        );

        create index if not exists ix_object_labels_object_id
            on labels.object_labels (object_id);

        create index if not exists ix_object_labels_label_id
            on labels.object_labels (label_id);

        create index if not exists ix_object_labels_object_type
            on labels.object_labels (object_type);

        create index if not exists ix_object_labels_type_obj_time
            on labels.object_labels (object_type, object_id, attached_at, label_id);
    """


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
