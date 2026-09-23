"""
EssayCards — Sprint10_DualSchedulerAB migration backfill tests.

Verifies the two guarded schema.sql migration UPDATEs directly against the
database, by inserting a raw pre-Sprint10-shaped flashcard_review_state row
(scheduler_assigned_at left NULL, exactly as any row created before this
sprint would be) and re-running schema.sql's DDL (it is idempotent and
re-executable by construction — the same file backend/database.py::
init_schema() runs on every application startup). No HTTP involved — this
exercises the SQL migration directly, independent of the FastAPI app.

Traceability: each function name maps to a scenario in
Sprint10_DualSchedulerAB/10_test_spec.md.
"""

import os

import pytest


def _run_schema_sql(db_conn) -> None:
    """Re-execute the canonical schema.sql — the exact mechanism
    backend/database.py::init_schema() and tests/conftest.py's setup_schema
    fixture already use. Idempotent DDL; the migration backfill's own
    scheduler_assigned_at IS NULL guard is what this test suite exercises."""
    schema_path = os.path.join(os.path.dirname(__file__), "../schema.sql")
    with open(schema_path) as f:
        ddl = f.read()
    with db_conn.cursor() as cur:
        cur.execute(ddl)


def _insert_legacy_row(db_conn, flashcard_id: str, essay_id: str, section_id: str,
                        card_key: str, last_reviewed_at_expr: str | None,
                        next_due_at_expr: str, review_interval_expr: str | None = None) -> None:
    """Insert one flashcard + a PRE-SPRINT10-shaped flashcard_review_state row
    (scheduler columns left at their column DEFAULT/NULL, exactly as any row
    written before this sprint's migration columns existed)."""
    with db_conn.cursor() as cur:
        cur.execute(
            "insert into essaycards.flashcards (id, essay_id, section_id, card_key, question, answer) "
            "values (%s, %s, %s, %s, 'q', 'a')",
            (flashcard_id, essay_id, section_id, card_key),
        )
        if review_interval_expr:
            cur.execute(
                f"insert into essaycards.flashcard_review_state "
                f"(flashcard_id, last_reviewed_at, next_due_at, review_interval) "
                f"values (%s, {last_reviewed_at_expr}, {next_due_at_expr}, {review_interval_expr})",
                (flashcard_id,),
            )
        else:
            cur.execute(
                f"insert into essaycards.flashcard_review_state "
                f"(flashcard_id, last_reviewed_at, next_due_at) "
                f"values (%s, {last_reviewed_at_expr}, {next_due_at_expr})",
                (flashcard_id,),
            )


# fix-migration-* cards live under the existing Essay A / Section A1 fixture
# (see tests/fixtures.sql) — this file only needs a valid essay_id/section_id
# to satisfy the flashcards FK, not a dedicated essay.
ESSAY_A = "ea000001-0000-0000-0000-000000000001"
SECTION_A1 = "ec000001-0000-0000-0000-000000000001"

FC_MIGRATION_LEGACY_REVIEWED = "fc0000f1-0000-0000-0000-0000000000f1"
FC_MIGRATION_NEVER_REVIEWED = "fc0000f2-0000-0000-0000-0000000000f2"
FC_MIGRATION_RERUN = "fc0000f3-0000-0000-0000-0000000000f3"


def test_migration_assigns_legacy_reviewed_cards_to_classic_without_touching_due_dates(db_conn):
    """Scenario: Migration backfill retains previously-reviewed cards on
    Classic without altering their schedule — a row that predates this
    sprint with a non-null last_reviewed_at is assigned scheduler='classic',
    scheduler_assignment_reason='legacy_retained_classic', and its
    next_due_at/review_interval/last_reviewed_at are byte-for-byte
    unchanged; no fsrs_card_state row is created for it."""
    _insert_legacy_row(
        db_conn, FC_MIGRATION_LEGACY_REVIEWED, ESSAY_A, SECTION_A1, "fix-migration-legacy",
        last_reviewed_at_expr="now() - interval '17 days'",
        next_due_at_expr="now() - interval '3 days'",
        review_interval_expr="interval '14 days'",
    )
    with db_conn.cursor() as cur:
        cur.execute(
            "select last_reviewed_at, next_due_at, review_interval "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_MIGRATION_LEGACY_REVIEWED,),
        )
        before = cur.fetchone()

    _run_schema_sql(db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler, scheduler_assignment_reason, scheduler_assigned_at, "
            "last_reviewed_at, next_due_at, review_interval, experiment_version "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_MIGRATION_LEGACY_REVIEWED,),
        )
        after = cur.fetchone()

    assert after["scheduler"] == "classic"
    assert after["scheduler_assignment_reason"] == "legacy_retained_classic"
    assert after["scheduler_assigned_at"] is not None
    assert after["experiment_version"] == "sprint10_v1"
    assert after["last_reviewed_at"] == before["last_reviewed_at"]
    assert after["next_due_at"] == before["next_due_at"]
    assert after["review_interval"] == before["review_interval"]

    with db_conn.cursor() as cur:
        cur.execute(
            "select 1 from essaycards.fsrs_card_state where flashcard_id = %s",
            (FC_MIGRATION_LEGACY_REVIEWED,),
        )
        assert cur.fetchone() is None


def test_migration_assigns_never_reviewed_existing_cards_via_balanced_mechanism(db_conn):
    """Scenario: Migration backfill assigns never-reviewed existing cards via
    the balanced mechanism — a row that predates this sprint with a null
    last_reviewed_at receives a scheduler via the same balanced mechanism as
    a brand-new card, scheduler_assignment_reason='migrated_never_reviewed_random',
    and its next_due_at is unchanged."""
    _insert_legacy_row(
        db_conn, FC_MIGRATION_NEVER_REVIEWED, ESSAY_A, SECTION_A1, "fix-migration-never-reviewed",
        last_reviewed_at_expr="null",
        next_due_at_expr="now() - interval '2 hours'",
    )
    with db_conn.cursor() as cur:
        cur.execute(
            "select next_due_at from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_MIGRATION_NEVER_REVIEWED,),
        )
        before_next_due_at = cur.fetchone()["next_due_at"]

    _run_schema_sql(db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler, scheduler_assignment_reason, scheduler_assigned_at, next_due_at "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_MIGRATION_NEVER_REVIEWED,),
        )
        after = cur.fetchone()

    assert after["scheduler"] in ("classic", "fsrs")
    assert after["scheduler_assignment_reason"] == "migrated_never_reviewed_random"
    assert after["scheduler_assigned_at"] is not None
    assert after["next_due_at"] == before_next_due_at


def test_migration_backfill_is_idempotent_on_rerun(db_conn):
    """Scenario: Migration backfill is idempotent on rerun — re-executing
    schema.sql (as happens on every application startup) after the backfill
    has already run once for a row is a no-op: no reassignment, no
    record-count change."""
    _insert_legacy_row(
        db_conn, FC_MIGRATION_RERUN, ESSAY_A, SECTION_A1, "fix-migration-rerun",
        last_reviewed_at_expr="null",
        next_due_at_expr="now() - interval '1 hour'",
    )

    _run_schema_sql(db_conn)
    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler, scheduler_assignment_reason, scheduler_assigned_at "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_MIGRATION_RERUN,),
        )
        first = cur.fetchone()

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.flashcard_review_state")
        count_before = cur.fetchone()["n"]

    _run_schema_sql(db_conn)  # second rerun — must be a no-op for this already-migrated row

    with db_conn.cursor() as cur:
        cur.execute(
            "select scheduler, scheduler_assignment_reason, scheduler_assigned_at "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_MIGRATION_RERUN,),
        )
        second = cur.fetchone()
        cur.execute("select count(*) as n from essaycards.flashcard_review_state")
        count_after = cur.fetchone()["n"]

    assert second == first  # including scheduler_assigned_at — not touched again
    assert count_after == count_before
