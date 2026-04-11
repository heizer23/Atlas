#!/usr/bin/env python3
"""
Sync prod database to test database.

Drops atlas_test, recreates it, then pipes pg_dump atlas | psql atlas_test
entirely inside the Postgres container — fast, no network transfer.

Use this for manual exploratory testing against realistic data.
Do NOT call this as part of automated test runs — tests use SQL fixtures instead.

Usage:
    python3 01_System/test/sync_db.py
    # or via Makefile:
    make -C 01_System test-sync-db
"""

import subprocess
import sys

POSTGRES_CONTAINER = "atlas-postgres"
PROD_DB = "atlas"
TEST_DB = "atlas_test"
PG_USER = "atlas"


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"FAILED: {cmd}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def main() -> None:
    print(f"Syncing {PROD_DB} → {TEST_DB} (inside {POSTGRES_CONTAINER})...")

    # Terminate any connections to atlas_test so we can drop it
    run(
        f'docker exec {POSTGRES_CONTAINER} psql -U {PG_USER} -d postgres -c '
        f'"SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
        f'WHERE datname = \'{TEST_DB}\' AND pid <> pg_backend_pid();"'
    )

    # Drop and recreate
    run(f'docker exec {POSTGRES_CONTAINER} psql -U {PG_USER} -d postgres -c "DROP DATABASE IF EXISTS {TEST_DB};"')
    run(f'docker exec {POSTGRES_CONTAINER} psql -U {PG_USER} -d postgres -c "CREATE DATABASE {TEST_DB};"')

    # Dump prod → test (pipe stays inside the container, very fast)
    run(
        f'docker exec {POSTGRES_CONTAINER} bash -c '
        f'"pg_dump -U {PG_USER} {PROD_DB} | psql -U {PG_USER} -d {TEST_DB} -q"'
    )

    print("Done. atlas_test is now a copy of atlas.")
    print(f"Test stack UI:  http://localhost:9080")
    print(f"Note: test runs will truncate and reload fixtures — synced data will be replaced.")


if __name__ == "__main__":
    main()
