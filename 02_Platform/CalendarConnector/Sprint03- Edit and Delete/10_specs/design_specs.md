# Design Specs — CalendarConnector Sprint03: Edit and Delete

**Reviewer:** sprint_specs_reviewer
**Date:** 2026-04-05
**Sprint:** Sprint03- Edit and Delete
**Component:** 02_Platform/CalendarConnector

---

## Verdict

**READY**

All three open questions are resolved below. The draft is well-scoped, internally consistent with Sprint02 patterns, and contains sufficient product decisions for designer handoff. Remaining gaps are all safe designer choices.

---

## Open Question Resolutions

### OQ1 — Should deleted index rows be retained as `deleted` or hard-deleted?

**Resolution: retain as `deleted`.**

The draft itself marks `retain as deleted` as the preferred answer. This is confirmed correct by two codebase constraints:

1. The index purpose includes "Preserve stable cross-system linkage" and "Provide a minimal upgrade path toward stronger internal ownership later" — hard deleting index rows undermines both.
2. Idempotent delete behavior (draft line 168: "if no active mapping exists, return idempotent success") requires the system to distinguish between "never existed" and "existed then was deleted." A hard delete collapses these two cases and makes idempotency semantically weaker: a re-create after a delete would always succeed (no ambiguity), but a later delete retry would find no row and would not know whether the event was already deleted or was never created. Retaining the row with `status='deleted'` makes the idempotent delete path deterministic and auditable.

**Decision:** On successful remote delete, set `status = 'deleted'` on the index row. Never remove the row. Future create with the same `atlas_event_id` after a delete must treat the old row as superseded — either insert a new row or reactivate the existing one (see OQ2 for state machine; designer may reactivate by updating the existing row back to `active` on re-create).

### OQ2 — When a mapped Google event is missing during update/delete, what state should the index entry become?

**Resolution: `error` for update; `deleted` for delete.**

These two operations have different intents when the remote event is missing:

**Update — set status to `error`:**
An update request for a missing Google event is an unambiguous data integrity problem. The Atlas side believes the event exists (active mapping), but Google has no record. This is not recoverable by the system alone — it may indicate manual deletion by the operator in Google Calendar, a Google-side purge, or an index inconsistency. Setting status to `error` signals a broken mapping that requires operator attention. The endpoint must return an explicit error (`GOOGLE_EVENT_NOT_FOUND`) and record `last_error` on the index row with enough context to diagnose. The caller must not silently succeed on an update for a non-existent event.

Consistent with draft line 165: "If the mapped Google event is missing remotely, return an explicit error and record it in both decision log and index state."

**Delete — set status to `deleted`:**
A delete request for a missing Google event is idempotent-friendly. The goal of delete is that the event no longer exists in Google Calendar. If Google already has no record of it (manual deletion, prior delete, Google purge), the desired outcome is already achieved. Marking the index row as `deleted` is correct: it closes the lifecycle cleanly and prevents future update or delete attempts from attempting to resolve a non-existent event. The endpoint must return idempotent success (not an error) and record a decision log entry with a note that the remote event was absent.

This aligns with draft line 187: "Delete is idempotent when no active mapping exists."

**Decision table:**

| Operation | Remote event missing | Index status set to | HTTP response |
|-----------|---------------------|---------------------|---------------|
| PATCH     | Yes                 | `error`             | 404 with `GOOGLE_EVENT_NOT_FOUND` |
| DELETE    | Yes                 | `deleted`           | 200 success (idempotent) |
| POST (create, active mapping exists) | N/A | unchanged (`active`) | 200 with existing event data |

**Index status vocabulary:** `active`, `deleted`, `error` — these are the only three valid values for the `status` column.

### OQ3 — Should create response distinguish newly-created vs. existing-mapping-returned?

**Resolution: yes, the `status` field must distinguish the two cases.**

Rationale: the caller (OpenClaw skill) needs to know whether it caused a new Google event to be created or is receiving a cached reference. This affects:
- Whether to update the caller's own state (e.g., store a new google_event_id vs. confirm an existing one)
- Debuggability: if OpenClaw retries a create and receives `status: "existing"` instead of an error, it knows the idempotency mechanism worked correctly

The `CalendarCreateEventResult` model in `app/models.py` currently hardcodes `status: str = "created"`. This must be changed to an open field. Sprint02's model was acceptable for a pure-create endpoint; Sprint03 repurposes the same endpoint to handle idempotent returns, so the distinction must be surfaced.

**Decision:** The create response (`CalendarCreateEventResult`) must use `status: "created"` when a new Google event was inserted and `status: "existing"` when an existing active mapping was returned without calling Google. Both cases return the same shape. The `atlas_event_id` field (absent from the current Sprint02 model — see Must-Fix section) must be included in both.

No separate response model is needed. A single model with `status: Literal["created", "existing"]` is sufficient.

---

## Must-Fix Issues (Blocking)

### MF1 — `atlas_event_id` is absent from the Sprint02 create response model and must be added for Sprint03

**Issue:** `CalendarCreateEventResult` in `app/models.py` does not include `atlas_event_id`. Sprint03 makes this field mandatory: the event index maps `atlas_event_id` to `google_event_id`, and the create/update/delete responses all declare `atlas_event_id` as a required response field in the draft's Data Contract section (line 107).

**Why it blocks:** The designer cannot define the response model for the updated create endpoint, or the update/delete response models, without knowing whether `atlas_event_id` is retrofitted into the existing `CalendarCreateEventResult` model or a new shared model is introduced. This is a model ownership decision, not a visual choice.

**Minimal fix:** Add `atlas_event_id: str` to `CalendarCreateEventResult`. This is a non-breaking addition for callers that were ignoring the field. Create and update share the same response shape (draft lines 104-114); the designer must produce a single model that covers both. The designer may rename `CalendarCreateEventResult` to `CalendarEventOperationResult` or keep the name — that is their choice.

### MF2 — PATCH and DELETE route shapes require clarification: path param or body?

**Issue:** The draft declares:
```
PATCH /api/calendar/events
DELETE /api/calendar/events
```
Both have only `atlas_event_id` as a required field. The draft does not specify whether `atlas_event_id` is supplied as a path parameter (`/api/calendar/events/{atlas_event_id}`), a query parameter, or a request body field.

**Why it blocks:** This is a product-defined API contract. The caller (OpenClaw skill) must agree on the call shape. Two designers would make different choices here.

**Minimal fix (resolution provided):**

- **PATCH:** `atlas_event_id` in the URL path: `PATCH /api/calendar/events/{atlas_event_id}`. Patch body contains only the fields being updated. This follows REST conventions for partial update of a named resource. The designer must require that the body contain at least one updatable field (draft line 95).

- **DELETE:** `atlas_event_id` in the URL path: `DELETE /api/calendar/events/{atlas_event_id}`. No body. This follows REST conventions for deletion of a named resource and avoids the semantically awkward DELETE-with-body pattern.

This resolves to:
```
POST   /api/calendar/events                        — create (idempotent)
PATCH  /api/calendar/events/{atlas_event_id}       — update
DELETE /api/calendar/events/{atlas_event_id}       — delete (idempotent)
```

---

## Safe-to-Defer Decisions (Designer can handle)

**Migration file naming:** The next migration should be `migrations/003_event_index.sql`. Designer confirms numbering against the existing `001_init.sql` and `002_write_capability.sql`.

**Index table name:** The draft does not name the table. `calendar_event_index` is the natural choice. Designer may name it differently; the name is local to this component.

**Postgres index on `atlas_event_id`:** The `atlas_event_id` column on the event index table should carry a `UNIQUE` constraint (it is the lookup key). Whether to also add a non-unique index on `status` for filtering is a designer choice. Not required at this scale.

**Re-create after delete — row reuse vs. new row:** When a create arrives for an `atlas_event_id` whose index row has `status='deleted'`, the designer may either reactivate the existing row (UPDATE back to `active`) or insert a new row (leaving the old deleted row as historical trace). Both are valid. Reactivation is simpler; inserting a new row preserves cleaner history. Either satisfies the spec's minimal persistence principle.

**Decision log `operation` values for new operations:** Sprint02 defined `'calendar_event_create'`. The designer must define operation strings for update and delete (e.g., `'calendar_event_update'`, `'calendar_event_delete'`). These are internal audit strings only; the exact values are a designer choice.

**`atlas_event_id` storage on Google event:** The draft requires (line 152): "All created Google events must carry the stable atlas_event_id in Google event metadata." The Google Calendar API supports extended properties (`extendedProperties.private` or `shared`). The designer must implement storage of `atlas_event_id` in the event body sent to Google on create. The exact Google field path (`extendedProperties.private.atlas_event_id`) is a designer choice, but the requirement is mandatory.

**Token refresh logic for PATCH and DELETE:** The existing token-refresh pattern (lazy refresh before the Google API call) must be replicated in the PATCH and DELETE endpoint handlers. The designer may extract this into a shared helper function rather than duplicating the ~40-line block three times. Refactoring into a helper is acceptable and preferred, but is a designer choice.

---

## Atlas Violations / Redundancies

**No violations found.** The spec correctly:

- Does not use `Dataset` for create/update/delete responses (R-CON-BP-04 §8 — Dataset applies to data-returning reads only)
- Uses `api_error()` for all error responses (R-CON-BP-04 §5)
- Does not accept `calendar_id` from callers (enforces the invariant established in Sprint02)
- Restricts writes to the dedicated Chronos-Dates calendar (R-CON-PL-01 — platform component does not encode application-specific workflow decisions, but the fixed target calendar is an operator deployment constraint, not application domain logic)
- References existing platform contracts (`platform_contracts.contracts`, `platform_errorhandling.api_response`) without redefining them

**Potential redundancy to watch:** The draft mentions "decision log entry for every operation attempt" (line 15 and line 153). Sprint02 already defined the `calendar_decision_log` table and `write_decision_log()` function. Sprint03 must extend, not redefine, these. The designer must add new `operation` values to the existing log table — not create a separate log table for update/delete operations.

---

## Ambiguities with Suggested Resolution

**Ambiguity 1:** What HTTP status code does `PATCH /api/calendar/events/{atlas_event_id}` return on success?

**Suggested resolution:** `200 OK` with the updated event reference (same shape as create success minus the `status: "created"/"existing"` distinction — update always returns `status: "updated"`). Using `204 No Content` would discard the event reference, which the caller needs. Confidence: **High**.

**Ambiguity 2:** What is returned in the delete success response? Draft says `status`, `atlas_event_id`, `google_event_id when known`.

**Suggested resolution:** A minimal struct: `{ status: "deleted", atlas_event_id: str, google_event_id: Optional[str] }`. `google_event_id` is `None` when the index row had no active mapping at all (truly idempotent case where no index row existed). `google_event_id` is present when the index row existed (including the case where the remote event was already missing and the row was marked `deleted`). Confidence: **High**.

**Ambiguity 3:** When the event index has `status='error'` for a given `atlas_event_id` and a create request arrives for that same ID, what happens?

**Suggested resolution:** Treat `error` status as non-active. A create request for an `atlas_event_id` with `status='error'` must proceed to create the event in Google (same as the "no active mapping" path). This allows recovery from a broken mapping by re-issuing the create. The designer should reactivate or replace the error-status row. Confidence: **Medium** — the draft does not address this case explicitly, but the principle "Idempotency is part of the slice: retries must be safe" supports treating error-status as non-blocking for a re-create.

**Ambiguity 4:** Should `PATCH` also preserve the `atlas_event_id` in Google event metadata (same as create)?

**Suggested resolution:** Yes. The Google event update call (events.patch or events.update) must not remove the `atlas_event_id` from `extendedProperties`. The draft requires (line 164): "Preserve atlas_event_id metadata on the Google event." This is a mandatory requirement, not a designer choice. The designer must include the `extendedProperties` field in the PATCH body sent to Google. Confidence: **High**.

---

## Risks

**Risk 1: Token refresh duplication — Medium**
The token refresh block is ~40 lines in `calendar.py` and is already duplicated between `get_events` and `create_event`. Sprint03 adds two more endpoints. If the designer does not extract this into a shared helper, the router module will have ~120 lines of duplicated token refresh logic. Not a correctness risk, but a maintenance risk. The designer should extract `_get_valid_access_token(conn)` as a shared internal function. Flag if implementation review sees further duplication.

**Risk 2: Partial failure on create — index inconsistency — High (carry-forward from draft)**
The draft is explicit (line 159): if Google creation succeeds but index persistence fails, treat as failed and surface the error. This is stricter than the Sprint02 decision log behavior (best-effort). The designer must implement a two-phase check: Google create first, then index write. If the index write fails, the operation must return an error (not silently succeed), even though the Google event now exists. This creates a potential orphaned Google event. The designer must document this known inconsistency in `architecture.json` risks — it is an accepted trade-off for this slice.

**Risk 3: PATCH routing conflict with existing POST on `/api/calendar/events` — Low**
FastAPI supports multiple HTTP methods on the same path without conflict. `POST /api/calendar/events` and `PATCH /api/calendar/events/{atlas_event_id}` are distinct routes. No conflict.

**Risk 4: `atlas_event_id` uniqueness assumption — Medium**
The event index requires `atlas_event_id` to be unique (it is the lookup key). The spec assumes callers supply stable, unique `atlas_event_id` values. No validation of `atlas_event_id` format is specified. If OpenClaw sends a duplicate `atlas_event_id` for what is semantically a different event, the idempotency behavior will return the existing mapping, which may surprise the caller. The designer should enforce `UNIQUE(atlas_event_id)` at the DB level (Postgres constraint) so conflicts are explicit rather than silent. This is a `UNIQUE` constraint decision, not a format validation decision.

**Risk 5: Re-create after delete and the Sprint02 `CalendarCreateEventRequest` model — Low**
Sprint02's `CalendarCreateEventRequest` does not include `atlas_event_id`. Sprint03's idempotent create depends entirely on `atlas_event_id` as the lookup key (draft line 26). This field is missing from the existing request model. The designer must add `atlas_event_id: str` as a required field to `CalendarCreateEventRequest`. This is a breaking change to the Sprint02 POST endpoint contract. However, since Sprint02 is currently `AWAITING_HUMAN_REVIEW` and has no external consumers yet, this is low risk in practice. The designer must note this in `implementation_notes.md`.

---

## Sprint02 Context for Designer

The following Sprint02 artifacts are complete and must be treated as the authoritative baseline:

- `app/routers/calendar.py` — 5 endpoints; PATCH and DELETE must be added here; `create_event` must be updated for idempotency
- `app/models.py` — `CalendarCreateEventRequest` (add `atlas_event_id`), `CalendarCreateEventResult` (add `atlas_event_id`, make `status` an open field); new models for update response and delete response required
- `app/services/calendar_api.py` — `create_event()` exists; new `update_event()` and `delete_event()` functions required
- `app/services/token_store.py` — `write_decision_log()` exists; new functions for event index CRUD required (`upsert_event_index()`, `get_event_index_by_atlas_id()`, `mark_event_index_deleted()`, `mark_event_index_error()`)
- `migrations/002_write_capability.sql` — existing schema; add `migrations/003_event_index.sql` for the new index table

**Known pre-existing gap (do not make worse):** `connect_callback` atomicity — noted in Sprint01 implementation review. Not in scope.

---

## Minimal Edits to Reach READY

Not applicable — verdict is READY with open questions resolved above. The Must-Fix items (MF1, MF2) are resolved in this document and do not require changes to the draft before design proceeds. They are designer instructions.

---

## Summary of Resolved Decisions

| Decision | Resolution |
|---|---|
| Deleted index row retention | Retain as `deleted` — never hard delete |
| Index state: Google event missing during PATCH | Set status to `error`; return 404 `GOOGLE_EVENT_NOT_FOUND` |
| Index state: Google event missing during DELETE | Set status to `deleted`; return idempotent success |
| Create response: new vs. existing | `status: "created"` for new; `status: "existing"` for returned mapping |
| PATCH URL shape | `PATCH /api/calendar/events/{atlas_event_id}` |
| DELETE URL shape | `DELETE /api/calendar/events/{atlas_event_id}` |
| `atlas_event_id` in request model | Add as required field to `CalendarCreateEventRequest` |
| `atlas_event_id` in response model | Add to `CalendarCreateEventResult`; retrofit Sprint02 model |
| Index status vocabulary | `active`, `deleted`, `error` only |
| Error-status index row behavior on re-create | Treat as non-active; proceed to create |
| PATCH success HTTP status | `200 OK` with updated event reference |
| Delete success response shape | `{ status: "deleted", atlas_event_id, google_event_id? }` |
| `atlas_event_id` preservation on PATCH to Google | Mandatory — include in `extendedProperties` on update call |
| Decision log for new operations | Extend existing `calendar_decision_log`; add operation values `calendar_event_update`, `calendar_event_delete` |
| Migration file | `migrations/003_event_index.sql` |
