# Design Review — CalendarConnector Sprint02-Writing Skill

**Reviewer:** sprint_design_reviewer
**Date:** 2026-04-05
**Sprint:** Sprint02-Writing Skill
**Component:** 02_Platform/CalendarConnector

---

## Verdict

**APPROVED**

The design is complete, internally consistent, Atlas-aligned, and safe to hand off to the platform implementer. All invariants are explicit, failure modes are exhaustive, and the scaffolding is actionable. No corrections required.

---

## Checklist

### 1. Platform boundary (R-CON-PL-01)

- CalendarConnector provides a reusable technical capability (Google Calendar write via OAuth). No domain logic is embedded. The caller (Chronos skill) decides what events to create; the connector owns only the transport, credential lifecycle, target enforcement, and audit persistence. PASS.
- No 03_Application imports in the design. PASS.
- No user_id FK on any table. PASS.

### 2. Contracts and boundaries (R-CON-BP-02)

- Public interfaces are explicit: POST /api/calendar/events is fully specified with request shape, response shape, all failure modes, and target enforcement invariant.
- Dependency direction is correct: CalendarConnector consumes platform packages and external APIs; nothing consumes it except the calling skill.
- Caller cannot override target calendar ID — enforced via env var, not request body. Invariant explicitly stated. PASS.

### 3. No hidden state (R-CON-BP-03)

- New `calendar_decision_log` table is defined in `migrations/002_write_capability.sql` with explicit schema, owner, and lifecycle.
- `CALENDAR_TARGET_CALENDAR_ID` env var is explicitly declared as required deployment input.
- No implicit state introduced. PASS.

### 4. Architecture as AI interface (R-CON-BP-01)

- architecture.json and scaffolding.json together provide a deterministic implementation roadmap.
- All design decisions are recorded with rationale.
- The relationship between the scope upgrade, re-consent requirement, and INSUFFICIENT_SCOPE check is clearly explained.
- PASS.

### 5. Scope invariant check

The INSUFFICIENT_SCOPE check implementation guidance in scaffolding.json is correct:
- `'https://www.googleapis.com/auth/calendar' in (connection['granted_scopes'] or '')` correctly distinguishes write-capable scope from the read-only substring `calendar.readonly`.
- Edge case (space-separated scope strings in arbitrary order) is handled by substring containment, not exact equality. PASS.

### 6. Decision log best-effort semantics

- Invariant states: "A decision log write failure must never cause the endpoint to return an error if the Google API call succeeded." Explicitly confirmed in both architecture.json invariants and internal_flow step 6. PASS.
- The scaffolding's `write_decision_log` docstring correctly places best-effort responsibility on the caller (router layer). PASS.

### 7. init_schema() multi-file fix

- Correctly identified as a correctness requirement (not a deferral) in design_decisions.
- Scaffolding specifies the fix: sorted glob over migrations/ directory, execute each file in a separate transaction in order. PASS.

### 8. Dataset contract (R-CON-BP-04)

- POST /api/calendar/events returns a structured JSON success payload, not a Dataset. This is correct — Dataset applies to data-surfacing read endpoints.
- Read endpoints (GET /api/calendar/events, GET /api/calendar/status) continue to return Dataset. PASS.
- Error responses use api_error(). PASS.

### 9. No breaking changes to existing endpoints

- GET /api/calendar/events: unchanged flow, unchanged Dataset shape. PASS.
- GET /api/calendar/status: unchanged flow. PASS.
- OAuth scope change in connect_start is additive: calendar scope is a superset of calendar.readonly. Existing read functionality continues to work. PASS.

### 10. Failure modes

All failure modes from the draft are covered:
- INSUFFICIENT_SCOPE — new
- CALENDAR_TARGET_NOT_CONFIGURED — new (startup fail-fast)
- CALENDAR_TARGET_NOT_FOUND — new
- NO_CALENDAR_CONNECTION — reused
- CONNECTION_EXPIRED / CONNECTION_REVOKED — reused
- GOOGLE_API_ERROR — reused
- INVALID_EVENT_INPUT — new (422 via FastAPI Pydantic validation)
- DB_UNAVAILABLE — reused

PASS.

### 11. Deployment preconditions

Both preconditions are explicitly documented in architecture.json `deployment_preconditions`:
1. CALENDAR_TARGET_CALENDAR_ID in config.env
2. Re-consent via GET /api/calendar/google/connect/start

PASS.

---

## Minor Observations (non-blocking)

- The `_target_calendar_id()` helper is specified in scaffolding.json as "raise RuntimeError if absent (fail-fast — called at startup validation)". The implementer should add this call to `app/main.py` `on_startup()` alongside `init_pool()` and `init_schema()`. This is consistent with the existing startup pattern.

- `CalendarCreateEventResult.all_day` is typed as `bool` in scaffolding.json. The existing `CalendarEventRow.all_day` is typed as `str` ("true"/"false") for Dataset compatibility reasons. The POST response is not a Dataset row, so using native `bool` is correct and preferred. The distinction is clear and intentional. No inconsistency.

- The scaffolding leaves `FastAPI 422 validation errors` (missing required fields) to FastAPI's built-in handling. This is acceptable — FastAPI returns a structured `detail` array on 422, not an `api_error()` envelope. This is a known Atlas pattern inconsistency (all other errors use api_error()) but is pre-existing behavior across all Atlas services and not in scope to fix here.

---

## Summary

| Dimension | Result |
|---|---|
| Platform boundary | PASS |
| Contracts and boundaries | PASS |
| No hidden state | PASS |
| Architecture as AI interface | PASS |
| Scope invariant check | PASS |
| Decision log best-effort | PASS |
| init_schema() fix | PASS |
| Dataset contract | PASS |
| Backward compatibility | PASS |
| Failure modes | PASS |
| Deployment preconditions | PASS |

**Verdict: APPROVED**
