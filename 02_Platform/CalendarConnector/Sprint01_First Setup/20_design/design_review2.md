# Design Review — calendar_connector (Iteration 2)

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: All three required corrections from the first review are verified resolved at the design artifact level. The migration runner gap has a closed recorded decision in `design_decisions`. The nginx block is reclassified to `internal_required` with upstream shape fully declared. `CALENDAR_CONNECTOR_PORT=8021` is registered in `config.env` and referenced by env var name in `architecture.json`. One pre-existing duplication issue (`python-jose`/`PyJWT` appearing in both `external_required` and `external_optional`) was flagged in the first review's Scaffold-Only Observations but was not in the Minimal Change Set and was not corrected — it must be resolved before implementation to prevent an unconditional spurious dependency. All other design content remains sound and implementable.

---

## Confirmed Problems

1. **`python-jose or PyJWT` duplicated across `external_required` and `external_optional`**
   - Severity: Major
   - Location: `20_design/architecture.json` → `dependencies.external_required[5]` and `dependencies.external_optional[0]`
   - Why it is a problem: The same library (`python-jose or PyJWT`) appears in both lists with identical role descriptions. `external_required` means the dependency is unconditionally required. `external_optional` means it is conditional on an implementer path decision. These are mutually exclusive classifications. The library is only needed if the implementer decodes Google's `id_token` to extract `account_email`; if the userinfo endpoint path is chosen instead, the library is not needed at all.
   - Impact: An implementer following `external_required` strictly will add `python-jose` or `PyJWT` to `pyproject.toml` unconditionally, introducing a dependency that may be unnecessary. The first review flagged this; it was not corrected by the design corrections pass.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the optional nature of the library was identified but the `external_required` entry was not removed when the `external_optional` entry was added.

---

## Recommended Improvements

None identified beyond the confirmed problem above.

---

## Scaffold-Only Observations

1. **`logs/` directory has no bind-mount declaration in `compose.yml` stub**
   - Location: `20_design/scaffolding.json` → `directories` (`02_Platform/CalendarConnector/logs`) and `files` entry for `compose.yml`
   - Observation: The `logs/` directory is scaffolded but the `compose.yml` stub declares no volume mount for it. `platform_errorhandling.setup_logging()` accepts a `log_dir` argument — if logs are written inside the container without a bind-mount, they are lost on container restart.
   - Impact on implementation: Implementer must decide whether to add a bind-mount or accept ephemeral logs. Either is acceptable, but the decision should be explicit in the compose stub.

---

## Hard Rule Violations

None identified.

---

## Open Uncertainties

1. **`connect_callback` atomicity across `upsert_connection` and `upsert_token`**
   - Location: `20_design/architecture.json` → `internal_flow[1]` (connect_callback), `dependencies.internal_required` (token_store.py interface)
   - Uncertainty: The design does not specify whether the two DB writes in the callback flow (upsert_connection then upsert_token) must execute within a single transaction. The `token_store.py` interface accepts a shared `conn` parameter on both functions, which enables transactional use, but atomicity is not declared as a requirement. A partial-state failure (connection row present, token row absent) is not covered by any declared failure mode.
   - Why it matters: Non-transactional writes create a reachable undefined behavior path: `get_connection()` returns a row, `get_token()` returns None, and no failure mode handler covers this state.
   - Suggested owner: Implementer

---

## Minimal Change Set

1. Remove `dependencies.external_required[5]` (`python-jose or PyJWT`) from `architecture.json` — the entry in `external_optional` is the correct and sufficient declaration for this conditional dependency.

---

## Approval Condition

`python-jose or PyJWT` must be removed from `dependencies.external_required` so that `external_required` contains only unconditional dependencies before implementation begins.
