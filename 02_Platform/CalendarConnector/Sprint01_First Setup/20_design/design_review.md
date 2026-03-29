# Design Review — calendar_connector (Iteration 3)

## Verdict
- Status: APPROVED
- Summary: All corrections required by the first and second reviews have been fully applied and verified. The migration runner is a closed design decision in `design_decisions`. Nginx is classified `internal_required` with upstream shape explicitly declared. `CALENDAR_CONNECTOR_PORT=8021` is registered in `01_System/config.env` and referenced by env var name in `architecture.json`. The `python-jose`/`PyJWT` duplication has been resolved — the entry exists only in `external_optional` and is absent from `external_required`. The design is complete, implementable, and compliant with all applicable Atlas rules.

---

## Confirmed Problems

None identified.

---

## Recommended Improvements

None identified.

---

## Scaffold-Only Observations

1. **`logs/` directory has no bind-mount declaration in `compose.yml` stub**
   - Location: `20_design/scaffolding.json` → `directories` (`02_Platform/CalendarConnector/logs`) and `files` entry for `compose.yml`
   - Observation: The `logs/` directory is scaffolded but the `compose.yml` stub declares no volume mount for it. `platform_errorhandling.setup_logging()` accepts a `log_dir` argument — if logs are written inside the container without a bind-mount, they are lost on container restart.
   - Impact on implementation: Implementer must decide whether to add a bind-mount or accept ephemeral logs. Either is acceptable for this slice, but the choice must be explicit in the compose file.

---

## Hard Rule Violations

None identified.

---

## Open Uncertainties

1. **`connect_callback` atomicity across `upsert_connection` and `upsert_token`**
   - Location: `20_design/architecture.json` → `internal_flow[1]` (connect_callback), `dependencies.internal_required` (token_store.py interface)
   - Uncertainty: The design does not specify whether the two DB writes in the callback flow (`upsert_connection` then `upsert_token`) must execute within a single transaction. The `token_store.py` interface accepts a shared `conn` parameter on both functions, which enables transactional use, but atomicity is not declared as a requirement. A partial-state failure (connection row present, token row absent) is not covered by any declared failure mode.
   - Why it matters: Non-transactional writes create a reachable undefined behavior path — `get_connection()` returns a row but `get_token()` returns None — with no failure mode handler for that state.
   - Suggested owner: Implementer

---

## Minimal Change Set

None required.

---

## Approval Condition

All previously required corrections are verified applied. The design is approved for implementation.

---

## Four-Point Correction Verification (Iteration 3 Checklist)

| Condition | Status | Evidence |
|---|---|---|
| Migration runner — closed design decision present | Confirmed | `architecture.json` → `design_decisions[0]`: `database.py init_schema()` declared as authoritative schema deployment path; `migrate.py` extension deferred to future infrastructure sprint |
| Nginx — `internal_required` with upstream shape | Confirmed | `architecture.json` → `dependencies.internal_required[3]`: entry classifies `02_Platform/02_Atlas_Shell/nginx.conf`, declares upstream `atlas-calendar-connector:8000`, `proxy_pass`, four headers, and `proxy_read_timeout` |
| Port — `CALENDAR_CONNECTOR_PORT=8021` in `01_System/config.env` | Confirmed | `01_System/config.env` line 21: `CALENDAR_CONNECTOR_PORT=8021`; `architecture.json` references env var by name, not raw port |
| `python-jose`/`PyJWT` only in `external_optional`, absent from `external_required` | Confirmed | `architecture.json` → `dependencies.external_required`: five entries (fastapi, uvicorn, psycopg2-binary, httpx, pydantic) — no JWT library present; `dependencies.external_optional[0]`: `python-jose or PyJWT` with conditional role description |
