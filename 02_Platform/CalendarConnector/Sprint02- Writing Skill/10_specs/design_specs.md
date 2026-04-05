# Design Specs — CalendarConnector Sprint02-Writing Skill

**Reviewer:** sprint_specs_reviewer
**Date:** 2026-04-05
**Sprint:** Sprint02-Writing Skill
**Component:** 02_Platform/CalendarConnector

---

## Verdict

**READY**

The draft is well-scoped, Atlas-aligned, and internally consistent. Three open questions raised by the author are resolved below. The designer has all necessary context to proceed.

---

## Open Question Resolutions

### OQ1 — Dedicated Chronos calendar ID storage: config value vs DB setting

**Resolution: config value in `01_System/config.env`.**

Codebase inspection shows no existing Postgres-based "persisted settings" infrastructure. Introducing a DB-backed settings mechanism for a single calendar ID would add complexity disproportionate to the value. The Atlas pattern for system-scoped, operator-supplied identifiers is `config.env` (e.g., `MCP_BASE_URL`, `NOTIFICATIONS_DISPATCH_INTERVAL_SECONDS`).

The dedicated Chronos calendar ID is an operator-supplied deployment input, not runtime state. Storing it in config is the simpler, more consistent choice.

**Decision:** Add `CALENDAR_TARGET_CALENDAR_ID` to `01_System/config.env`. The CalendarConnector reads this env var at request time. The designer must document this as a required deployment input.

### OQ2 — Decision log contract: new table or existing?

**Resolution: new table, this slice defines it.**

No existing `decision_log` table exists in the Atlas codebase. The only reference to "decision log" in the repository is in an agent to-do file — it is not an implemented platform contract.

The designer must define a `calendar_decision_log` table as part of this sprint's migration artifact. The draft's field requirements are sufficient to define the schema. No cross-component contract coordination is required.

**Decision:** Add a `calendar_decision_log` table in a new migration (`migrations/002_write_capability.sql`). Fields: `id` (serial PK), `operation` (text, e.g. `'calendar_event_create'`), `requested_at` (timestamptz), `target_calendar_id` (text), `outcome` (text: `'success'` or `'failure'`), `google_event_id` (text, nullable), `error_summary` (text, nullable), `created_at` (timestamptz default now()).

### OQ3 — All-day event support in this first write slice

**Resolution: support `all_day` as an optional field, timed events are the primary case.**

The existing read path already normalizes `all_day` as a string field. For the write path, the simplest consistent approach is: if `all_day=true` is supplied, use Google's `date`-only start/end format; if absent or false, use `dateTime` format. This avoids special-casing without over-designing.

**Decision:** `all_day` is an optional boolean-style field in the create request. If `all_day=true`, format `start_at`/`end_at` as date strings (YYYY-MM-DD) in the Google API call. If absent or false, use dateTime format. The designer must handle both cases in the Google Calendar API write call.

---

## Sprint01 Context for Designer

The following Sprint01 implementation artifacts are complete and must be treated as the authoritative baseline:

- `app/routers/calendar.py` — 4 existing endpoints; new `POST /api/calendar/events` must be added here
- `app/services/google_oauth.py` — OAuth helpers; `build_authorization_url()` must be updated to support write scope
- `app/services/calendar_api.py` — read-only event fetch; a new `create_event()` function must be added
- `app/services/token_store.py` — DB access helpers; new `write_decision_log()` function required
- `app/models.py` — existing row shapes; new `CalendarCreateEventRequest` and `CalendarCreateEventResult` models required
- `migrations/001_init.sql` — existing schema; add `migrations/002_write_capability.sql` for new table
- `app/database.py` — `init_schema()` runs all SQL files in migrations/ — designer must verify this handles multiple files

**Known gap to address (from Sprint01 implementation_review.md):** `connect_callback` atomicity — `upsert_connection()` and `upsert_token()` share a `with get_db()` block but each calls `conn.commit()` internally. This is a pre-existing gap; it is not in scope for this sprint but must not be made worse.

---

## Atlas Alignment Checks

### OAuth scope upgrade path

The current `build_authorization_url()` in `google_oauth.py` requests `calendar.readonly` scope only. Upgrading to write scope requires requesting `https://www.googleapis.com/auth/calendar`. The safest upgrade path is:

- Change the scope in `build_authorization_url()` to `calendar` (which includes read + write)
- Require a fresh re-consent: the existing `connect_start` flow uses `prompt=consent` already, so running it again will produce a new grant with the expanded scope
- The existing `calendar_connection` and `calendar_token` tables do not need schema changes — `granted_scopes` already captures what was granted
- **No token migration is required.** The operator simply re-runs the connect flow after the code is deployed

The designer must document in `architecture.json` that the write-capable scope change requires the operator to re-run the OAuth consent flow (`GET /api/calendar/google/connect/start`) after deployment.

### Scope value change

Current: `https://www.googleapis.com/auth/calendar.readonly`
Required: `https://www.googleapis.com/auth/calendar`

The `calendar` scope is a superset of `calendar.readonly`. Existing read functionality continues to work with the broader scope.

### Invariant: caller cannot override target calendar

The draft mandates that `POST /api/calendar/events` must not accept a `calendar_id` from the caller. The target calendar is always the value of `CALENDAR_TARGET_CALENDAR_ID` env var. This must be stated as an invariant in the architecture design.

### Decision log write must not block event create response

The decision log write is a side-effect of the create operation. A failure to write the decision log must not cause the endpoint to return an error to the caller if the Google API call itself succeeded. Log the failure internally and continue. If the Google API call fails, the decision log write should still be attempted (best-effort). This avoids a partial-failure state where the event is created but the log write fails silently and the caller receives an error.

Design note: implement decision log write as try/except, log any DB error, never propagate it to the caller.

### Dataset contract does not apply to the POST response

`POST /api/calendar/events` is a create operation, not a data-returning read. It must return a structured JSON success payload (not a `Dataset`) as specified in the draft's Data Contract section. This is explicitly permitted by R-CON-BP-04 §8 — `Dataset` applies to endpoints that surface data to the UI. The error response must still use `api_error()` per R-CON-BP-04.

### Route placement

New endpoint: `POST /api/calendar/events` — consistent with existing `/api/calendar/` namespace. No new nginx block required (existing `/api/calendar` location block in nginx.conf already covers this path).

---

## Must-Fix Issues for Designer (Blocking)

None — the draft is implementation-ready after open question resolution above.

---

## Safe-to-Defer Decisions (Designer can handle)

**Scope constant naming:** Designer may choose whether to update `_CALENDAR_SCOPE` constant to a new value, or add a separate `_CALENDAR_WRITE_SCOPE` constant and select between them. Either is acceptable.

**Decision log index:** Whether to add a Postgres index on `calendar_decision_log.requested_at` is a designer choice. Not required for this slice's scale.

**`connect_start` scope detection:** Whether to expose a parameter to `connect_start` to hint the desired scope level (so UI could trigger a write-capable consent vs. read-only consent) is out of scope for this slice. The designer may simplify by always requesting write-capable scope in `connect_start`.

---

## Risks

**Re-consent requirement — High visibility**
The OAuth scope upgrade requires the operator to re-run the consent flow. This must be documented clearly in the architecture design and implementation notes as a deployment pre-condition, alongside the existing callback URI registration requirement.

**`CALENDAR_TARGET_CALENDAR_ID` missing at runtime — High**
If the env var is not set and CalendarConnector starts up, the first write request will fail. The designer should decide whether to validate this at startup (fail-fast) or at request time (return api_error). Fail-fast startup validation is preferred — raise `RuntimeError` if the env var is absent, consistent with how `_client_id()` and `_client_secret()` work in `google_oauth.py`.

**Google Calendar API write quota — Low**
Google Calendar API has per-user write quotas. For a system-scoped single-connection deployment, this is not a practical concern for this slice. No mitigation required.

**database.py init_schema() multi-file handling — Medium**
Sprint01 `init_schema()` was written for a single migration file. If it only executes `001_init.sql` by name, the new `002_write_capability.sql` will not run on startup. The designer must verify `init_schema()` handles all `.sql` files in `migrations/` sorted by filename, or adapt it to do so. This is a correctness requirement, not a deferral.

---

## Summary of Resolved Decisions

| Decision | Resolution |
|---|---|
| Calendar target ID storage | `CALENDAR_TARGET_CALENDAR_ID` in `01_System/config.env` |
| Decision log contract | New `calendar_decision_log` table, defined in `migrations/002_write_capability.sql` |
| All-day support | Optional field; `true` uses date-only format, absent/false uses dateTime format |
| OAuth scope upgrade path | Change scope to `calendar`, operator re-runs consent flow post-deployment |
| POST response shape | Structured JSON success payload (not Dataset) — Dataset rule does not apply to create operations |
| Target calendar enforcement | Always from env var `CALENDAR_TARGET_CALENDAR_ID`; caller cannot override |
| Decision log write failure handling | Best-effort; never propagate log write failure to caller |
| Nginx changes | None required — existing `/api/calendar` block covers new POST route |
| New migration file | `migrations/002_write_capability.sql` |
