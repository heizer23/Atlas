"""
EssayCards — Sprint12_FSRSAndUXOverhaul migration tests.

Verifies three things directly against the database, independent of the
FastAPI app:
  1. schema.sql's backup table (essaycards.pre_fsrs_migration_backup_sprint12)
     is created and populated exactly once, before the Sprint10
     scheduler-assignment columns it snapshots are dropped.
  2. Those columns (flashcard_review_state's four + review_events.scheduler)
     no longer exist after migration.
  3. backend/migrate_fsrs_state.py::migrate_legacy_fsrs_state backfills
     essaycards.fsrs_card_state for a reviewed card with no native FSRS state,
     never touches next_due_at/review_interval/last_reviewed_at, skips a card
     that already has state, and is idempotent on rerun.

schema.sql has already run once per test (tests/conftest.py's setup_schema
session fixture, plus a rerun on every `client` fixture entry via FastAPI's
startup handler) — so the backup table and column drops are already in
effect by the time any test here runs. These tests confirm that end state and
exercise the Python backfill directly.

Traceability: each function name maps to a scenario in
Sprint12_FSRSAndUXOverhaul/10_test_spec.md.
"""

import os

from backend.migrate_fsrs_state import migrate_legacy_fsrs_state
from backend.scheduling import estimate_initial_fsrs_state


def _run_schema_sql(db_conn) -> None:
    """Re-execute the canonical schema.sql — idempotent, re-executable by
    construction (the same file backend/database.py::init_schema() runs on
    every application startup)."""
    schema_path = os.path.join(os.path.dirname(__file__), "../schema.sql")
    with open(schema_path) as f:
        ddl = f.read()
    with db_conn.cursor() as cur:
        cur.execute(ddl)


# fix-migration-* cards live under the existing Essay A / Section A1 fixture
# (see tests/fixtures.sql) — this file only needs a valid essay_id/section_id
# to satisfy the flashcards FK, not a dedicated essay.
ESSAY_A = "ea000001-0000-0000-0000-000000000001"
SECTION_A1 = "ec000001-0000-0000-0000-000000000001"

FC_BACKFILL_TARGET = "fc0000f1-0000-0000-0000-0000000000f1"

# Fixture card with real review history and NO fsrs_card_state row (see
# tests/fixtures.sql "fix-legacy-no-fsrs-state") — already backfilled by the
# time any test here runs, since the startup migration already fired at
# least once against it.
FC_LEGACY_NO_FSRS_STATE = "fc000030-0000-0000-0000-000000000030"

# Fixture card that already carries fsrs_card_state (fix-fsrs-established).
FC_ALREADY_HAS_STATE = "fc000023-0000-0000-0000-000000000023"


def test_backup_table_snapshots_pre_migration_scheduler_data_once(db_conn):
    """Scenario: the backup table is created and populated from pre-migration
    data, and a rerun does not duplicate or overwrite it."""
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.pre_fsrs_migration_backup_sprint12")
        before = cur.fetchone()["n"]
    assert before > 0  # populated from whatever rows existed pre-drop

    _run_schema_sql(db_conn)

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.pre_fsrs_migration_backup_sprint12")
        after = cur.fetchone()["n"]
    assert after == before  # rerun is a no-op — table already exists


def test_scheduler_columns_are_dropped_from_flashcard_review_state_and_review_events(db_conn):
    """Scenario: the four flashcard_review_state scheduler columns and
    review_events.scheduler no longer exist after migration."""
    with db_conn.cursor() as cur:
        cur.execute(
            "select column_name from information_schema.columns "
            "where table_schema = 'essaycards' and table_name = 'flashcard_review_state'"
        )
        frs_columns = {r["column_name"] for r in cur.fetchall()}
        cur.execute(
            "select column_name from information_schema.columns "
            "where table_schema = 'essaycards' and table_name = 'review_events'"
        )
        review_events_columns = {r["column_name"] for r in cur.fetchall()}

    for col in ("scheduler", "scheduler_assigned_at", "scheduler_assignment_reason", "experiment_version"):
        assert col not in frs_columns
    assert "scheduler" not in review_events_columns


def test_experiment_summary_route_is_fully_removed(client):
    """Scenario: 'The dual-scheduler experiment is fully removed'. The
    Sprint10 A/B experiment router (backend/routers/experiment.py) was
    deleted this sprint along with its dashboard — GET
    /api/essaycards/experiment/summary must now 404 (the route does not
    exist), not return a scheduler-filtered empty result."""
    res = client.get("/api/essaycards/experiment/summary")
    assert res.status_code == 404


def test_legacy_fsrs_backfill_creates_state_for_reviewed_card_without_one(db_conn):
    """Scenario: a card with last_reviewed_at set and no fsrs_card_state row
    gets one, without altering next_due_at/review_interval/last_reviewed_at."""
    with db_conn.cursor() as cur:
        cur.execute(
            "insert into essaycards.flashcards (id, essay_id, section_id, card_key, question, answer) "
            "values (%s, %s, %s, 'fix-migration-backfill', 'q', 'a')",
            (FC_BACKFILL_TARGET, ESSAY_A, SECTION_A1),
        )
        cur.execute(
            "insert into essaycards.flashcard_review_state "
            "(flashcard_id, last_reviewed_at, next_due_at, review_interval) "
            "values (%s, now() - interval '17 days', now() - interval '3 days', interval '14 days')",
            (FC_BACKFILL_TARGET,),
        )
        cur.execute(
            "select last_reviewed_at, next_due_at, review_interval "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_BACKFILL_TARGET,),
        )
        before = cur.fetchone()

    migrate_legacy_fsrs_state(db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            "select stability, difficulty, fsrs_state, step, last_review_at, raw_state "
            "from essaycards.fsrs_card_state where flashcard_id = %s",
            (FC_BACKFILL_TARGET,),
        )
        state_row = cur.fetchone()
        cur.execute(
            "select last_reviewed_at, next_due_at, review_interval "
            "from essaycards.flashcard_review_state where flashcard_id = %s",
            (FC_BACKFILL_TARGET,),
        )
        after = cur.fetchone()

    assert state_row is not None
    assert state_row["fsrs_state"] == 2  # review_interval (14 days) >= 24h -> Review
    assert state_row["step"] is None
    assert after == before  # due dates / review_interval / last_reviewed_at untouched


def test_legacy_fsrs_backfill_skips_card_that_already_has_state(db_conn):
    """Scenario: a card that already has fsrs_card_state is left completely
    untouched by the backfill."""
    with db_conn.cursor() as cur:
        cur.execute(
            "select stability, difficulty, fsrs_state, step, last_review_at, raw_state "
            "from essaycards.fsrs_card_state where flashcard_id = %s",
            (FC_ALREADY_HAS_STATE,),
        )
        before = cur.fetchone()
    assert before is not None

    migrate_legacy_fsrs_state(db_conn)

    with db_conn.cursor() as cur:
        cur.execute(
            "select stability, difficulty, fsrs_state, step, last_review_at, raw_state "
            "from essaycards.fsrs_card_state where flashcard_id = %s",
            (FC_ALREADY_HAS_STATE,),
        )
        after = cur.fetchone()
    assert after == before


def test_legacy_fsrs_backfill_is_idempotent_on_rerun(db_conn):
    """Scenario: running the backfill twice produces the same end state, no
    duplicate rows, no second write."""
    fc_id = "fc0000f3-0000-0000-0000-0000000000f3"
    with db_conn.cursor() as cur:
        cur.execute(
            "insert into essaycards.flashcards (id, essay_id, section_id, card_key, question, answer) "
            "values (%s, %s, %s, 'fix-migration-rerun', 'q', 'a')",
            (fc_id, ESSAY_A, SECTION_A1),
        )
        cur.execute(
            "insert into essaycards.flashcard_review_state "
            "(flashcard_id, last_reviewed_at, next_due_at, review_interval) "
            "values (%s, now() - interval '2 hours', now() + interval '22 hours', interval '1 day')",
            (fc_id,),
        )

    migrate_legacy_fsrs_state(db_conn)
    with db_conn.cursor() as cur:
        cur.execute(
            "select stability, difficulty, raw_state from essaycards.fsrs_card_state where flashcard_id = %s",
            (fc_id,),
        )
        first = cur.fetchone()

    migrate_legacy_fsrs_state(db_conn)  # second run — must be a no-op for this already-migrated row
    with db_conn.cursor() as cur:
        cur.execute(
            "select stability, difficulty, raw_state from essaycards.fsrs_card_state where flashcard_id = %s",
            (fc_id,),
        )
        second = cur.fetchone()
        cur.execute("select count(*) as n from essaycards.fsrs_card_state where flashcard_id = %s", (fc_id,))
        count = cur.fetchone()["n"]

    assert second == first
    assert count == 1


def test_legacy_fsrs_backfill_already_ran_against_fixture_card_via_startup(client, db_conn):
    """Sanity check on tests/fixtures.sql's own legacy-no-fsrs-state fixture
    (fix-legacy-no-fsrs-state): by the time this test body runs, the startup
    migration has already fired at least once (the `client` fixture enters a
    fresh TestClient(app) context, which re-fires FastAPI's startup handler —
    see tests/conftest.py), so this reviewed, originally-state-less fixture
    card should already carry a synthesized fsrs_card_state row."""
    with db_conn.cursor() as cur:
        cur.execute(
            "select 1 from essaycards.fsrs_card_state where flashcard_id = %s",
            (FC_LEGACY_NO_FSRS_STATE,),
        )
        assert cur.fetchone() is not None


def test_exam_type_column_defaults_pre_sprint_rows_to_guided(db_conn):
    """Scenario: a section_examinations row inserted before this sprint's
    migration reads exam_type='guided' after migration. The fixture rows
    se-origins-1/se-origins-2 (tests/fixtures.sql) are inserted without an
    exam_type column at all, relying purely on the column DEFAULT."""
    with db_conn.cursor() as cur:
        cur.execute(
            "select exam_type from essaycards.section_examinations where id = %s",
            ("5e000001-0000-0000-0000-000000000001",),
        )
        row = cur.fetchone()
    assert row["exam_type"] == "guided"


def test_estimate_initial_fsrs_state_still_importable_and_pure():
    """Smoke check that the pure estimation helper used by the migration
    driver above is independently callable with no DB access."""
    from datetime import timedelta, datetime, timezone
    state = estimate_initial_fsrs_state(timedelta(days=2), datetime.now(timezone.utc) - timedelta(days=2))
    assert "raw_state" in state
