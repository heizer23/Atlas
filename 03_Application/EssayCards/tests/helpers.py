"""
Shared test helpers (Sprint14_SectionProgressionAndRevalidation).

Cards of an essay created through ingest / upsert start LOCKED (their section
has no guided pass). Tests that need to review or queue such cards unlock the
essay's sections explicitly — the same state a passing guided section oral
would create.
"""

import psycopg2
import psycopg2.extras

from tests.conftest import _build_url


def run_sql(sql: str, params: tuple = ()) -> list[dict]:
    """Execute one statement on a fresh autocommit connection; returns rows if any."""
    conn = psycopg2.connect(_build_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []
    finally:
        conn.close()


def unlock_essay_sections(essay_id: str) -> None:
    """Mark every section of the essay guided_passed (source 'grandfathered')."""
    run_sql(
        """
        insert into essaycards.section_oral_state (section_id, guided_passed, guided_pass_source)
        select id, true, 'grandfathered' from essaycards.essay_sections where essay_id = %s
        on conflict (section_id) do update
            set guided_passed = true,
                guided_pass_source = coalesce(essaycards.section_oral_state.guided_pass_source, 'grandfathered')
        """,
        (essay_id,),
    )
