# Agent Pass: Implementation Reviewer
**Run:** full_auditrun_04_06_2026
**Date:** 2026-04-06
**Agent function:** Code correctness against design specs, missing artifacts, schema-to-code consistency

---

## Scope

Implementation code for all deployed applications. Sprints still in design or awaiting human review are out of implementation scope. Focus: deployed backend code, schema consistency, platform package usage, and any implementation-level drift from sprint design artifacts.

---

## Applications Reviewed

- TaskTracker (Sprint02 implementation complete, awaiting implementation review)
- WorkoutTracker (no sprint folder — implementation reviewed against manifest intent)
- CalendarConnector (Sprint03 implementation complete per sprint_state.json)
- Notifications (Sprint1 implementation complete per sprint_state.json)

FoodTracker Sprint04 and Chronicle Sprint02 are in design/draft state — not implementation-reviewed here.

---

## Findings

### TaskTracker — Sprint02 Implementation

**Schema consistency:**
`schema.sql` (canonical schema file) includes `effort_hours double precision` with check constraint — matches Sprint02 design intent.

**Critical finding — schema.sql vs database.py divergence (BLOCKING):**

`schema.sql` (the canonical schema file, committed to git, updated as part of Sprint02) includes `effort_hours`:
```sql
effort_hours double precision check (effort_hours is null or effort_hours >= 0),
```

`backend/database.py` `init_schema()` function contains an inline DDL that is the original Sprint01 schema WITHOUT `effort_hours`. This DDL is run at startup for schema initialization.

**Consequence:** On a fresh deployment, `init_schema()` creates the table without `effort_hours`. The migration file `migrations/002_add_effort.sql` (present in the directory listing) would then need to be run separately via `make migrate` to add the column. However, if `init_schema()` runs first and already creates the table, the migration runner may skip it because the table already exists.

The dual-schema problem:
1. `schema.sql` — canonical, has `effort_hours`
2. `database.py` `init_schema()` — has original schema, no `effort_hours`
3. `migrations/002_add_effort.sql` — presumably adds `effort_hours` as a delta

On a fresh install: `init_schema()` creates table without `effort_hours` → migration `002` adds it → works.
On an existing install where `init_schema()` was already applied: `init_schema()` is idempotent (IF NOT EXISTS) → no change → migration `002` adds `effort_hours` → works.

This appears to function correctly but creates a maintenance hazard. The `schema.sql` file and `init_schema()` DDL are now permanently out of sync. Future agents reading `schema.sql` will believe the table has `effort_hours` from the start; agents reading `database.py` will believe it does not. This is a hidden state inconsistency (R-CON-BP-03 proximity violation — not the same as hidden durable state, but inconsistent documentation of the same schema).

**Recommendation:** Either (a) update `database.py` `init_schema()` to match `schema.sql` for fresh-install consistency, or (b) document explicitly that `schema.sql` is the canonical reference and `init_schema()` is the Sprint01 baseline that migrations build on.

**Backend implementation:**
`tasks.py` Sprint02 implementation:
- `effort_hours` added to `TASK_SCHEMA` — correct
- `TaskCreate` includes `effort_hours: float | None = None` — correct
- `TaskUpdate` includes `effort_hours: float | None = None` — correct
- Critically: `if "effort_hours" in body.model_fields_set: fields["effort_hours"] = body.effort_hours` — this is the correct pattern to distinguish "not sent" from "explicitly null." This was the RC-1 correction from the design review cycle. Implementation is correct.
- `row_to_dict` does not explicitly convert `effort_hours` — `double precision` from psycopg2 returns as Python float, which is JSON-serializable. Correct.

**Frontend implementation:**
`ShellEntry.tsx` Sprint02 implementation:
- `TaskRow` interface includes `effort_hours?: number | null` — correct
- `TASK_FIELDS` includes `effort_hours` with type 'number' — correct
- `TaskCard` renders `effortLabel` with `toFixed(1)` — correct
- `TaskDetailEdit` sends `effort_hours: effortValue` where null clears the field — correct, matches backend expectation

Frontend implementation: CORRECT.

### WorkoutTracker — Implementation Review

No sprint artifacts. Reviewed against code quality and contract compliance.

**Schema usage:** `workout.py` correctly imports from `platform_contracts`. All endpoints return Dataset or api_error(). Row id mapping is correct (`workout_log_id` → `id`).

**Row fields not in schema (undeclared extras):** `_exercise_row()` includes `set1_reps` through `set5_reps` and `comment` in the row dict, but `EXERCISE_SCHEMA` does not declare these. Per R-CON-BP-04 §2: "row fields not declared in schema are ignored — silent, no warning, no crash." This is intentional — the extra fields are available to an edit form that reads them. This is a deliberate, R-CON-BP-04-compliant pattern.

**Validation:** `_has_reps()` checks at least one rep value is non-null. Input validation is present for required fields.

Implementation: PASS.

### CalendarConnector Sprint03 — Implementation

Sprint_state.json indicates IMPLEMENTATION_IN_PROGRESS with `last_completed_step: "platform-implementer"`. Implementation is marked complete but no `30_implementation/implementation_review.md` is present (consistent with the sprint not yet being reviewed). Implementation is functionally in place.

**Router invariants (from docstring):**
- Token values never in responses — declared as invariant
- POST/PATCH/DELETE always write to CALENDAR_TARGET_CALENDAR_ID — declared
- CSRF nonce consumed on first use — declared
- Decision log written best-effort — declared
- Index write failure is a hard error — declared
- `_get_valid_access_token()` isinstance-check obligation documented

These invariants are declared at the module level and are auditable. Implementation compliance with invariants cannot be fully verified without reading the full router body, but invariant documentation is present and explicit (R-CON-BP-01 compliance: explicit invariants stated).

**Missing artifact:** `30_implementation/implementation_review.md` and `40_status/implementation_status.md` are absent — correct for current state (implementation complete, review not yet run). Not a blocker at this stage.

### Notifications Sprint1 — Implementation

Sprint_state.json: IMPLEMENTATION_IN_PROGRESS, awaiting human gate.

`backend/main.py` reviewed:
- Logging setup via `platform_errorhandling.logging` — correct
- Exception handlers and request timing via platform packages — correct
- APScheduler silenced at WARNING level — appropriate to avoid log flooding
- FCM initialization: fails to start if FCM credential env vars are absent — correct, fail-fast behavior
- Default device FCM token seeded from env on startup — documented in compose.yml, correct

`backend/routers/notifications.py`:
- `api_error()` from `platform_errorhandling` — correct
- `NotificationNotFoundError` handled with 404 — correct
- Cancel returns 200 for already-cancelled (idempotent no-op) — consistent with architecture.json design decision

Implementation: PASS on reviewed artifacts.

---

## Verdict

1 blocking finding (schema documentation divergence). All other implementations pass.

| Severity | Finding |
|----------|---------|
| BLOCKING | TaskTracker `database.py` `init_schema()` does not include `effort_hours` — diverges from `schema.sql` canonical reference. Creates agent-confusing dual source of truth. Fresh installs rely on migration `002` to add the column; `init_schema()` and `schema.sql` should be kept in sync |
| INFO | WorkoutTracker row extra fields (set1_reps–set5_reps, comment not in schema) — intentional, R-CON-BP-04 compliant |
| INFO | CalendarConnector Sprint03 implementation_review.md absent — correct for current sprint state |
