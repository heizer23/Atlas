# CLAUDE.md — 02_Platform/Postgres

## Migration system

Atlas uses a simple file-based migration runner (`migrate.py`). Applied migrations
are tracked in `public.schema_migrations`. `make migrate` is idempotent and safe
to run on every `make up`.

### Rules

1. **Migrations are immutable.** Never edit a migration file after it has been
   committed to git. If a change is needed, create a new migration.

2. **Filename format:** `NNN_description.sql` — zero-padded number, lowercase,
   underscores. Numbers must be unique within an app.
   Example: `003_add_notes_column.sql`

3. **Location:** `03_Application/<AppName>/migrations/`

4. **Write idempotent SQL where possible** (`IF NOT EXISTS`, `IF EXISTS`,
   `ON CONFLICT DO NOTHING`). This is not always possible for destructive
   operations (e.g. renaming a column), but aim for it.

5. **Wrap each migration in a transaction** (`BEGIN` / `COMMIT`) so a failure
   leaves the database unchanged.

### Creating a migration

```
03_Application/MyApp/migrations/
  001_init_schema.sql     ← first migration: full initial schema
  002_add_tags_column.sql ← delta only, not the full schema
```

Run `make migrate` — pending migrations are applied in filename order, per app
(apps processed alphabetically).

### Squashing

When history grows large, squash old migrations into a single file:

1. Create `NNN_squash.sql` containing the **full current schema** (idempotent).
2. Delete the old migration files that are now superseded.
3. On **existing databases**: the old filenames are already in `schema_migrations`,
   so the runner skips them. The new squash file runs as a normal new migration
   (idempotent, so it's a no-op on existing objects).
4. On **fresh databases**: only the squash file (and any subsequent migrations) run.

Squashing is an explicit, deliberate operation — not routine maintenance.
Do it when the number of migrations makes the history hard to follow.

### schema_migrations table

Lives in `public` (infrastructure, not an application). Columns:

| Column     | Type        | Description                        |
|------------|-------------|------------------------------------|
| id         | SERIAL      | Auto-increment PK                  |
| app        | TEXT        | Application folder name            |
| filename   | TEXT        | SQL filename                       |
| applied_at | TIMESTAMPTZ | When the migration was applied     |

Unique constraint on `(app, filename)`.
