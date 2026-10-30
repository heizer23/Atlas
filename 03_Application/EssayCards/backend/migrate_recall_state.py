"""
One-time, idempotent startup migration (Sprint16_RecallFSRS): seeds
essaycards.recall_state from legacy passed unguided orals.

Candidates: section_oral_state / essay_oral_state rows with unguided_passed = true
and no recall_state row yet. Each is seeded as ONE synthetic Good review dated at the
genuine unguided_passed_at (the old attempt's examined_at) — never "now" — so an old
pass is neither presented as newly completed nor given a fabricated timestamp, and
an overdue one simply reads as "due". This is a documented APPROXIMATION (R-OPS-BP-01):
the old 0-6 score carries no rating, so every legacy pass maps to Good.

No recall_reviews row is created (no review actually happened under the new
rubric) and section_examinations / essay_examinations are untouched evidence.
Legacy unguided_passed = false rows are NOT seeded: recall is "not established"
until demonstrated under the new format. Re-running selects nothing new.
"""

import logging
from typing import Any

from psycopg2.extras import Json

from backend.scheduling import recall_scheduler

log = logging.getLogger("essaycards")

_SECTION_SQL = """
    select es.essay_id, sos.section_id, sos.unguided_passed_at as passed_at
    from essaycards.section_oral_state sos
    join essaycards.essay_sections es on es.id = sos.section_id
    left join essaycards.recall_state rs on rs.section_id = sos.section_id and rs.scope = 'section'
    where sos.unguided_passed and sos.unguided_passed_at is not null and rs.id is null
"""
_ESSAY_SQL = """
    select eos.essay_id, null::uuid as section_id, eos.unguided_passed_at as passed_at
    from essaycards.essay_oral_state eos
    left join essaycards.recall_state rs on rs.essay_id = eos.essay_id and rs.scope = 'essay'
    where eos.unguided_passed and eos.unguided_passed_at is not null and rs.id is null
"""


def migrate_legacy_unguided_to_recall(conn: Any) -> dict[str, int]:
    """Returns {"seeded": int}. Each row is its own transaction; failures log and skip."""
    seeded = 0
    scheduler = recall_scheduler()
    for scope, sql in (("section", _SECTION_SQL), ("essay", _ESSAY_SQL)):
        with conn.cursor() as cur:
            cur.execute(sql)
            candidates = cur.fetchall()
        conn.commit()
        for row in candidates:
            try:
                result = scheduler.review("good", None, row["passed_at"], None)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into essaycards.recall_state
                            (scope, essay_id, section_id, raw_state, established_at, last_rating,
                             last_reviewed_at, next_due_at, review_count, lapse_count, source)
                        values (%s, %s, %s, %s, %s, 'good', %s, %s, 0, 0, 'migrated_exam')
                        on conflict do nothing
                        """,
                        (scope, row["essay_id"], row["section_id"], Json(result.extra_state["raw_state"]),
                         row["passed_at"], row["passed_at"], result.next_due_at),
                    )
                conn.commit()
                seeded += 1
            except Exception as exc:
                conn.rollback()
                log.error("recall seed skipped (%s %s): %s", scope, row["section_id"] or row["essay_id"], exc)
    return {"seeded": seeded}
