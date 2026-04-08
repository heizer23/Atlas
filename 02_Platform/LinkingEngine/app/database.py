"""
LinkingEngine — database connection pool and schema initialization.

Pattern: identical to TaskTracker and CalendarConnector.
Owns the 'linking' schema in the shared Postgres instance.
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
    """Create linking schema tables idempotently and seed relation_definitions."""
    schema_path = Path(__file__).parent.parent / "Sprint01_First Linking" / "20_Data" / "schema.sql"
    if not schema_path.exists():
        # Fallback: inline DDL (same content as schema.sql, used in deployments
        # where the sprint folder is not present alongside the app)
        _run_inline_ddl()
        return
    ddl = schema_path.read_text()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()


def _run_inline_ddl() -> None:
    """Inline DDL fallback — kept in sync with 20_Data/schema.sql."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                create schema if not exists linking;

                create table if not exists linking.objects (
                    object_id    text        not null,
                    workspace_id text,
                    type         text        not null,
                    title        text,
                    created_at   timestamptz not null default now(),
                    updated_at   timestamptz not null default now(),
                    constraint objects_pkey primary key (object_id)
                );

                create index if not exists ix_objects_type_workspace
                    on linking.objects (type, workspace_id);

                create table if not exists linking.relation_definitions (
                    key                 text    not null,
                    forward_label       text    not null,
                    reverse_label       text    not null,
                    is_directional      boolean not null default true,
                    allowed_from_types  text[]  not null,
                    allowed_to_types    text[]  not null,
                    is_active           boolean not null default true,
                    sort_order          integer not null default 100,
                    constraint relation_definitions_pkey primary key (key)
                );

                create table if not exists linking.object_links (
                    id               uuid         not null default gen_random_uuid(),
                    workspace_id     text,
                    from_object_id   text         not null references linking.objects(object_id),
                    to_object_id     text         not null references linking.objects(object_id),
                    relation_key     text         not null references linking.relation_definitions(key),
                    created_by_type  text         not null default 'user',
                    created_by_id    text,
                    confidence       numeric(4,3) not null default 1.000,
                    source_run_id    text,
                    metadata_json    jsonb        not null default '{}',
                    created_at       timestamptz  not null default now(),
                    archived_at      timestamptz,
                    constraint object_links_pkey primary key (id),
                    constraint object_links_no_self_link check (from_object_id != to_object_id)
                );

                create unique index if not exists ux_object_links_active
                    on linking.object_links (
                        coalesce(workspace_id, ''),
                        from_object_id,
                        to_object_id,
                        relation_key
                    )
                    where archived_at is null;

                create index if not exists ix_object_links_from
                    on linking.object_links (from_object_id) where archived_at is null;

                create index if not exists ix_object_links_to
                    on linking.object_links (to_object_id) where archived_at is null;

                insert into linking.relation_definitions
                    (key, forward_label, reverse_label, is_directional,
                     allowed_from_types, allowed_to_types, is_active, sort_order)
                values
                    ('subtask_of', 'Parent Task', 'SubTasks', true,
                     ARRAY['task'], ARRAY['task'], true, 10),
                    ('related_to', 'Related Tasks', 'Related Tasks', false,
                     ARRAY['task', 'workout', 'meal'], ARRAY['task', 'workout', 'meal'], true, 20)
                on conflict (key) do nothing;
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
