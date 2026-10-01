"""
One-time, idempotent startup migration: backfills essaycards.fsrs_card_state
for every flashcard_review_state row with real review history and no native
FSRS state yet (10_architecture.json internal_flow step 4).

Invoked once from backend/main.py's startup sequence, immediately after
init_schema() (schema.sql) succeeds — the backfill needs the final
post-migration schema (fsrs_card_state already existing, the Sprint10
scheduler columns already dropped).

Guard: "no existing fsrs_card_state row for this flashcard_id". A rerun after
the first successful pass selects zero rows and makes zero changes — the
backup table (essaycards.pre_fsrs_migration_backup_sprint12) and the column
drops are schema.sql's concern, not this module's.

Each row is backfilled in its own small transaction, so one malformed/
unexpected historical row logs an error and is skipped rather than blocking
every other card's migration or startup entirely (10_architecture.json
§contracts.invariants, failure_modes). A skipped row remains without
fsrs_card_state until its next real review, at which point FSRSScheduler.review
starts it from a fresh fsrs.Card() exactly as it would for a never-reviewed
card — same safe fallback, not a hard failure.

Never writes next_due_at / review_interval / last_reviewed_at for an existing
card — those three columns are read-only inputs to the synthesis
(backend.scheduling.estimate_initial_fsrs_state), never targets of it
(DUE DATES PRESERVED).
"""

import logging
from typing import Any

from psycopg2.extras import Json

from backend.scheduling import DESIRED_RETENTION, estimate_initial_fsrs_state

log = logging.getLogger("essaycards")


def migrate_legacy_fsrs_state(conn: Any) -> dict[str, int]:
    """
    Selects every flashcard_review_state row with last_reviewed_at IS NOT NULL
    and no existing fsrs_card_state row, computes initial state per card via
    backend.scheduling.estimate_initial_fsrs_state, and INSERTs the resulting
    fsrs_card_state row in its own per-row transaction.

    Returns {"attempted": int, "succeeded": int, "skipped": int} for startup
    logging.
    """
    summary = {"attempted": 0, "succeeded": 0, "skipped": 0}

    with conn.cursor() as cur:
        cur.execute(
            """
            select frs.flashcard_id, frs.last_reviewed_at, frs.review_interval
            from essaycards.flashcard_review_state frs
            left join essaycards.fsrs_card_state fcs on fcs.flashcard_id = frs.flashcard_id
            where frs.last_reviewed_at is not null
              and fcs.flashcard_id is null
            """
        )
        candidates = cur.fetchall()
    conn.commit()

    for row in candidates:
        summary["attempted"] += 1
        flashcard_id = row["flashcard_id"]
        try:
            state = estimate_initial_fsrs_state(
                row["review_interval"], row["last_reviewed_at"], DESIRED_RETENTION
            )
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into essaycards.fsrs_card_state
                        (flashcard_id, stability, difficulty, fsrs_state, step, last_review_at, raw_state, updated_at)
                    values (%s, %s, %s, %s, %s, %s, %s, now())
                    on conflict (flashcard_id) do nothing
                    """,
                    (
                        flashcard_id,
                        state["stability"],
                        state["difficulty"],
                        state["fsrs_state"],
                        state["step"],
                        state["last_review_at"],
                        Json(state["raw_state"]),
                    ),
                )
            conn.commit()
            summary["succeeded"] += 1
        except Exception:
            conn.rollback()
            summary["skipped"] += 1
            log.exception(
                "migrate_legacy_fsrs_state: skipped flashcard_id=%s due to an error", flashcard_id
            )

    log.info(
        "migrate_legacy_fsrs_state: attempted=%d succeeded=%d skipped=%d",
        summary["attempted"], summary["succeeded"], summary["skipped"],
    )
    return summary
