---
name: CalendarConnector Sprint03 Pattern
description: Platform-layer event lifecycle sprint (create/update/delete with idempotency + Postgres event index); currently at DRAFT_READY
type: project
---

CalendarConnector Sprint03-Edit and Delete. Sprint is at SPECS_READY — `platform-designer` is next.

**Why:** Extends Sprint02 (write/create only) to full event lifecycle: idempotent create, update, delete, and a lightweight Postgres event index table mapping `atlas_event_id` to `google_event_id`.

**Key design constraints (resolved in 10_specs/design_specs.md):**
- All writes restricted to dedicated Chronos-Dates calendar (fixed, caller cannot override)
- `atlas_event_id` is the stable cross-system key; must be added to `CalendarCreateEventRequest` (breaking Sprint02 model change — acceptable, no external consumers yet)
- Event index is an index only — must not evolve into a full meeting model
- Idempotency required for both create and delete; delete is idempotent when no active mapping exists
- No background workers; synchronous only
- Decision log entry required for every operation attempt; extend existing `calendar_decision_log`
- If Google creation succeeds but index persistence fails, treat as failed (no silent inconsistency) — stricter than Sprint02 decision log best-effort rule

**Three open questions — resolved in design_specs.md:**
1. Retained vs. hard-delete: retain as `deleted` always
2. Index state when Google event missing: `error` for PATCH (return 404), `deleted` for DELETE (return idempotent success)
3. Create response distinction: `status: "created"` for new; `status: "existing"` for returned mapping

**Final API shape:**
- POST   /api/calendar/events                        — create (idempotent)
- PATCH  /api/calendar/events/{atlas_event_id}       — update
- DELETE /api/calendar/events/{atlas_event_id}       — delete (idempotent)

**Index status vocabulary:** `active`, `deleted`, `error` (only three valid values)

**Migration:** `migrations/003_event_index.sql` — new `calendar_event_index` table (name is designer's choice).

**Model changes required:**
- `CalendarCreateEventRequest`: add `atlas_event_id: str` (required)
- `CalendarCreateEventResult`: add `atlas_event_id: str`; change `status` to open field (values: "created", "existing", "updated")
- New delete response model: `{ status: "deleted", atlas_event_id: str, google_event_id: Optional[str] }`

**token_store.py additions needed:** `upsert_event_index()`, `get_event_index_by_atlas_id()`, `mark_event_index_deleted()`, `mark_event_index_error()`

**calendar_api.py additions needed:** `update_event()`, `delete_event()` — PATCH must preserve `atlas_event_id` in Google extendedProperties

**Risk to flag in implementation review:** Token refresh block is ~40 lines duplicated per endpoint; designer should extract `_get_valid_access_token()` helper.
