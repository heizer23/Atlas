# Design Corrections — Calendar

## Applied Changes

1. **Replace asyncpg with psycopg2**
   - Review Source: `11_design_review.md §Blocking Issues #1`
   - Files Updated: `10_architecture.json`, `10_scaffolding.json`
   - Change: Replaced all `asyncpg` references with `psycopg2` (RealDictCursor pattern). In architecture.json: updated `dependencies.external_required` entry and `internal_flow` step 3 description and `deferrals.application_implementer`. In scaffolding.json: updated `backend/db.py` role and public_objects (replaced `get_pool`/`close_pool` with `get_connection`/`put_connection` pattern consistent with Atlas apps), updated `repository.py` role and method args (pool: asyncpg.Pool → conn: psycopg2.extensions.connection), updated `conftest.py` fixture purpose.

2. **Add schema.sql to scaffold**
   - Review Source: `11_design_review.md §Blocking Issues #2`
   - Files Updated: `10_scaffolding.json`
   - Change: Added `03_Application/Calendar/schema.sql` entry to `files[]` array as the runtime schema loaded idempotently at application startup, consistent with TaskTracker and StorageTracker patterns.

## Unchanged by Design

All sections not referenced by the Minimal Change Set — including all endpoints, data model, mapper, test spec, schema constraints, FullCalendar dependency, shell registration, and test scenarios — are preserved verbatim.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — asyncpg replaced with psycopg2 throughout; schema.sql added to scaffold
- Notes: None
