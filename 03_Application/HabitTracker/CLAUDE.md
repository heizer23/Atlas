# CLAUDE.md

This file contains app-local guidance only.
Global architecture and development rules are defined in the repository root CLAUDE.md.

## App
HabitTracker is a personal habit tracker built around one evening ritual: review today
(or any day), confirm which configured habits were actually done, and later see how
consistent that has been. Fast and comfortable on mobile — used once a day, every day.
All inputs are manual this sprint; automatic activity feeds (workouts, flashcards,
blood pressure) are explicitly deferred to a later sprint (see `source` column below).

## Day model (the one piece of real logic — `backend/review_logic.py`)

A day is identified by its Europe/Berlin calendar date and has exactly one of three
states, determined entirely by whether and how `habittracker.daily_reviews` has a row
for that date — there is no stored "unreviewed" row:

- **Unreviewed** — no row. The review view is computed fresh from current habit
  definitions.
- **Draft** — the user changed at least one checkbox; persists across reloads but is
  excluded from report counts/rates.
- **Confirmed** — the user tapped Confirm day. `confirmed_at` is stamped and the day
  counts in reports.

**Checked value on an Unreviewed/Draft day**: a saved `habit_results` row (from a prior
draft save) wins; otherwise the habit's *current* `default_checked` is used. Editing a
habit's default therefore never changes an already-saved draft/confirmed value — it
only supplies the starting value for a habit the draft hasn't seen yet.

**Confirmed day display is frozen**: `GET /reviews/{date}` for a Confirmed day returns
exactly the saved `habit_results` rows for that date (joined to each habit's *current*
name/description for display only), never recomputed from current habit active-window
state. Archiving or editing a habit after the fact never changes a previously confirmed
day's displayed habit set or values.

**PUT expected-set rule**: if the day's row exists AND is already `confirmed` *before*
the call, the expected `habit_id` set is the frozen set (whatever was last saved).
Otherwise it is `resolve_active_habits_for_date(date)` computed fresh. This is what lets
a correction to an old confirmed day succeed even if a habit's active window has since
changed, while a brand-new Unreviewed/Draft day always validates against the live set.

All three functions above — `resolve_active_habits_for_date`, `get_review_view`,
`compute_expected_habit_ids` — plus `resolve_report_period` live in exactly one place,
`backend/review_logic.py`, and are imported by `backend/routers/reviews.py` and
`backend/routers/reports.py`. Never re-implement any of them a second time.

## Reporting cell states (`backend/routers/reports.py::_cell_state`)

For each (habit, date) in the requested period:
- `completed` / `not_completed` — a `habit_results` row exists AND that date's status is
  `confirmed`.
- `unreviewed` — every other case where a row exists but the date is still `draft`, or
  no row exists but the habit's *current* active window covers the date.
- `not_active` — no row exists AND the habit's current active window excludes the date.

Note the asymmetry with the Daily Review frozen-display rule: here, the presence of a
saved row (confirmed OR draft) decides `not_active` vs. the rest — a habit's current
window only matters when no row exists at all for that date.

## `GET /reports` response shape

Returns a `Dataset` (one row per habit) **plus** an additive top-level sibling field,
`period_summary` (day-level period stats: `confirmed_days`, `elapsed_days`, the period's
`dates`, etc.) — not foldable into any single habit row. Built via
`response_model=None` + `dataset.model_dump(by_alias=True, mode="json")` +
`JSONResponse(content={**dict, "period_summary": {...}})`, the same pattern as
EssayCards' `backend/routers/review_stats.py::_dataset_response()`. `period_start` /
`period_end` are `.isoformat()`-converted before the merge (they bypass pydantic's JSON
serializer otherwise and break `JSONResponse`'s stdlib `json.dumps()` on a raw `date`).
`period_summary.anchor_date` is always the original, unparsed request string — never the
`date` object parsed for `resolve_report_period`. `reports.py` keeps its own file-local
`_parse_date_param`, a deliberate duplicate of `reviews.py`'s private helper of the same
name (not a cross-file import — that helper is explicitly scoped file-local to
`reviews.py`).

## Out of scope this sprint

No DELETE endpoint for habits — archiving (`end_date`) is the only retirement path. No
schedules/weekly-targets/quantities — every habit is daily. No automatic promotion of
`default_checked` based on performance. `habit_results.source` is reserved
(`'manual'` only, `CHECK`-enforced) for a later sprint's automatic data sources — no
integration exists yet.

## Port
HabitTracker backend runs on host port 8027 (container port 8000), bound to
`127.0.0.1` only (least exposure, R-OPS-BP-02) — the browser UI reaches it through
Atlas Shell's nginx reverse proxy over `atlas-net`.

## Schema
`habittracker` schema in the shared Atlas Postgres instance. Tables:
`habittracker.habits`, `habittracker.daily_reviews`, `habittracker.habit_results`.
Schema initialized idempotently at startup from `schema.sql`. The five starter habits
(Worked out / No sweets / No vaping / Measured blood pressure / Reviewed EssayCards) are
seeded once at startup by `backend/database.py::seed_starter_habits()`, idempotent by
table-emptiness (not by name) — a later rename never causes a duplicate reseed.

## Pattern references
Follow the same patterns as StorageTracker / StoryReader (03_Application):
- FastAPI backend, psycopg2 connection pool, RealDictCursor
- platform_contracts for Dataset responses on GET endpoints
- platform_errorhandling for api_error and middleware
- Atlas Shell registration via src/shellConfig.ts (mobilePrimaryNav primary target)
