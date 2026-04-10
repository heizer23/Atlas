#!/usr/bin/env python3
"""
Atlas migration runner.

Scans 03_Application/*/migrations/ for numbered SQL files, tracks applied
migrations in public.schema_migrations, and applies any pending ones.

Usage (via Makefile):
    make migrate

Direct usage (from repo root or 01_System/):
    python3 02_Platform/Postgres/migrate.py

Required env vars (exported by Makefile from config.env / secrets.env):
    ATLAS_PG_USER, ATLAS_PG_DB, ATLAS_PG_PASSWORD
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT       = Path(__file__).resolve().parents[2]
APPS_DIR        = REPO_ROOT / "03_Application"
PG_COMPOSE_FILE = Path(__file__).parent / "compose.yml"
SYSTEM_DIR      = REPO_ROOT / "01_System"


# ---------------------------------------------------------------------------
# psql helpers (all DB access goes through docker compose exec)
# ---------------------------------------------------------------------------

def _base_cmd() -> list[str]:
    return [
        "docker", "compose",
        "-f", str(PG_COMPOSE_FILE),
        "--env-file", str(SYSTEM_DIR / "config.env"),
        "--env-file", str(SYSTEM_DIR / "secrets.env"),
        "exec", "-T", "postgres",
        "psql",
        "-v", "ON_ERROR_STOP=1",
        "-U", os.environ["ATLAS_PG_USER"],
        "-d", os.environ["ATLAS_PG_DB"],
    ]


def _run(sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        _base_cmd() + ["-c", sql],
        capture_output=True, text=True,
    )


def _run_file(path: Path) -> subprocess.CompletedProcess:
    with open(path) as f:
        content = f.read()
    return subprocess.run(
        _base_cmd(),
        input=content,
        capture_output=True, text=True,
    )


def _query(sql: str) -> list[str]:
    """Run SQL and return non-empty output lines (tuples-only, unaligned)."""
    result = subprocess.run(
        _base_cmd() + ["-t", "-A", "-c", sql],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return [ln for ln in result.stdout.strip().splitlines() if ln]


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------

def ensure_migrations_table() -> None:
    r = _run("""
        CREATE TABLE IF NOT EXISTS public.schema_migrations (
            id         SERIAL      PRIMARY KEY,
            app        TEXT        NOT NULL,
            filename   TEXT        NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (app, filename)
        );
    """)
    if r.returncode != 0:
        print(f"ERROR creating schema_migrations:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)


def applied_migrations() -> set[tuple[str, str]]:
    rows = _query("SELECT app, filename FROM public.schema_migrations;")
    result = set()
    for row in rows:
        parts = row.split("|")
        if len(parts) == 2:
            result.add((parts[0], parts[1]))
    return result


def find_migrations() -> list[tuple[str, str, Path]]:
    """Return sorted (app, filename, path) for all migration files."""
    migrations = []
    for migrations_dir in sorted(APPS_DIR.glob("*/migrations")):
        app = migrations_dir.parent.name
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            migrations.append((app, sql_file.name, sql_file))
    return migrations


def record_migration(app: str, filename: str) -> None:
    r = _run(
        f"INSERT INTO public.schema_migrations (app, filename) "
        f"VALUES ('{app}', '{filename}');"
    )
    if r.returncode != 0:
        print(f"ERROR recording migration {app}/{filename}:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    print("==> Atlas migration runner")

    ensure_migrations_table()
    applied  = applied_migrations()
    all_migrations = find_migrations()
    pending  = [(a, f, p) for a, f, p in all_migrations if (a, f) not in applied]

    if not pending:
        print("    All migrations already applied.")
        return

    for app, fname, path in pending:
        print(f"    {app}/{fname} ...", end=" ", flush=True)
        r = _run_file(path)
        if r.returncode != 0:
            print("FAILED")
            print(r.stderr, file=sys.stderr)
            sys.exit(1)
        record_migration(app, fname)
        print("OK")

    print(f"==> {len(pending)} migration(s) applied.")


if __name__ == "__main__":
    main()
