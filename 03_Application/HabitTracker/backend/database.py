import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool

from backend.review_logic import berlin_today


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


# Fixed starter set, in display_order — 10_architecture.json internal_flow
# step 1 / 00_draft.md §Habit Definitions.
_STARTER_HABIT_NAMES: tuple[str, ...] = (
    "Worked out",
    "No sweets",
    "No vaping",
    "Measured blood pressure",
    "Reviewed EssayCards",
)


def seed_starter_habits() -> None:
    """If habittracker.habits is currently empty, insert the five starter
    rows. Called once at startup immediately after init_schema(). Idempotent
    by table-emptiness, not by name (contracts.invariants) — safe even after
    habits are renamed; a later rename does not cause a duplicate reseed on
    next restart, since the table is then non-empty regardless of what the
    rows are named.
    """
    today = berlin_today()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) as n from habittracker.habits")
            count = cur.fetchone()["n"]
            if count == 0:
                for display_order, name in enumerate(_STARTER_HABIT_NAMES):
                    cur.execute(
                        """
                        insert into habittracker.habits
                            (name, default_checked, display_order, active_from)
                        values (%s, false, %s, %s)
                        """,
                        (name, display_order, today),
                    )
        conn.commit()


# Linked habits (source -> display name). Done-ness comes from EssayCards.
LINKED_HABITS: tuple[tuple[str, str], ...] = (
    ("essaycards_flashcards", "Flashcards"),
    ("essaycards_oral", "Oral practice"),
)


def seed_linked_habits() -> None:
    """Insert each linked habit once (by source, even if later archived or
    renamed). active_from = first day EssayCards has such activity, so real
    history is shown; today if EssayCards is unreachable or has none."""
    from backend import essaycards_activity

    today = berlin_today()
    with get_db() as conn:
        with conn.cursor() as cur:
            for source, name in LINKED_HABITS:
                cur.execute("select 1 from habittracker.habits where source = %s", (source,))
                if cur.fetchone():
                    continue
                first = essaycards_activity.first_day(source) or today
                cur.execute(
                    """
                    insert into habittracker.habits (name, display_order, active_from, source)
                    values (%s, coalesce((select max(display_order) from habittracker.habits), -1) + 1, %s, %s)
                    """,
                    (name, first, source),
                )
        conn.commit()


# ── Categories & priorities seed ──────────────────────────────────────────────

_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("Body", "achievement"),
    ("Mind", "achievement"),
    ("Organization", "achievement"),
    ("Discipline", "discipline"),
)

_PRIORITIES: tuple[tuple[int, str, str], ...] = (
    (1, "Small", "Something is better than nothing"),
    (2, "Meaningful", "A worthwhile activity or achievement"),
    (3, "Major", "One of the important goals for the day"),
)

# One-time starting mapping for habits that existed before categories (matched by name /
# source). Starting suggestions only — editable in the app. Habits not listed stay uncategorised.
_LEGACY_MAPPING: dict[str, tuple[str, int]] = {
    "Worked out": ("Body", 3),
    "Wallangel": ("Body", 1),
    "Measured blood pressure": ("Body", 1),
    "Flashcards": ("Mind", 1),
    "Oral practice": ("Mind", 3),
    "Reviewed EssayCards": ("Mind", 2),
    "No sweets": ("Discipline", 1),
    "No vaping": ("Discipline", 2),
    "No Alc": ("Discipline", 2),
}


def seed_categories() -> None:
    """Seed priorities and the four initial categories once (idempotent by table-emptiness, so
    later renames/deletions never trigger a reseed). On that first run only, map existing
    uncategorised habits to categories/priorities via _LEGACY_MAPPING."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) as n from habittracker.habit_priorities")
            if cur.fetchone()["n"] == 0:
                for level, label, description in _PRIORITIES:
                    cur.execute(
                        "insert into habittracker.habit_priorities (level, label, description) values (%s, %s, %s)",
                        (level, label, description),
                    )
            cur.execute("select count(*) as n from habittracker.habit_categories")
            if cur.fetchone()["n"] == 0:
                for order, (name, kind) in enumerate(_CATEGORIES):
                    cur.execute(
                        "insert into habittracker.habit_categories (name, kind, display_order) values (%s, %s, %s)",
                        (name, kind, order),
                    )
                for habit_name, (cat, level) in _LEGACY_MAPPING.items():
                    cur.execute(
                        """
                        update habittracker.habits
                        set category_id = (select id from habittracker.habit_categories where name = %s),
                            priority = %s
                        where name = %s and category_id is null
                        """,
                        (cat, level, habit_name),
                    )
        conn.commit()


_SYMBOL_LAYER_BY_NAME = {"Body": "body", "Mind": "mind", "Organization": "organization", "Discipline": "discipline"}


def seed_symbol_layers() -> None:
    """Give the four initial categories their symbol layer once (only where still null, matched by
    their original names) so renaming a category later never breaks the symbol."""
    with get_db() as conn:
        with conn.cursor() as cur:
            for name, layer in _SYMBOL_LAYER_BY_NAME.items():
                cur.execute(
                    "update habittracker.habit_categories set symbol_layer = %s "
                    "where name = %s and symbol_layer is null "
                    "and not exists (select 1 from habittracker.habit_categories where symbol_layer = %s)",
                    (layer, name, layer),
                )
        conn.commit()
