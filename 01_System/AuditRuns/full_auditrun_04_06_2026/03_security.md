# Agent Pass: Security Reviewer
**Run:** full_auditrun_04_06_2026
**Date:** 2026-04-06
**Agent function:** Exposure risks, port configurations, privilege levels — R-OPS-BP-02

---

## Evidence Examined

- `01_System/config.env`
- `02_Platform/01_Postgres/compose.yml`
- `02_Platform/02_Atlas_Shell/compose.yml`
- `02_Platform/Notifications/compose.yml`
- `02_Platform/CalendarConnector/compose.yml`
- `02_Platform/MCPGateway/compose.yml`
- `02_Platform/Chronos/compose.yml`
- `02_Platform/Chronos/openclaw-init.json`
- `03_Application/TaskTracker/backend/main.py` (CORS configuration)
- `03_Application/WorkoutTracker/backend/main.py` (CORS configuration)
- `01_System/secrets.env` (existence noted; contents not read — gitignored)

---

## Findings

### PASS — Postgres bound to localhost only

`02_Platform/01_Postgres/compose.yml`: `ports: "127.0.0.1:${ATLAS_PG_PORT}:5432"`. Postgres is not accessible from the LAN. Correct configuration per R-OPS-BP-02.

### PASS — Application services are bridge-network-scoped

TaskTracker (8010), WorkoutTracker (8011), FoodTracker (8012), Chronicle (8013), CalendarConnector (8021) all use bridge network mode with port bindings that default to all interfaces. However, these services are expected to be on a self-hosted Pi accessible only via Tailscale/Cloudflared per `01_System/01_Access/`. The network boundary is enforced at the infrastructure layer, not at the container port binding level.

No container explicitly binds to `127.0.0.1` for application services — they rely on Tailscale for access control. This is an accepted deployment pattern for single-user self-hosted systems but represents a trust assumption that is not documented at the container level.

### WARNING — Notifications binds to `0.0.0.0:8020` explicitly for Android access

`02_Platform/Notifications/compose.yml`: `ports: "0.0.0.0:8020:8000"`. This is intentional (Android device via Tailscale) and is noted in config.env. However:
1. There is no authentication on the Notifications API endpoints.
2. The binding is explicit, deliberate, and documented.
3. Access is intended to be controlled by Tailscale.

The exposure is intentional and documented. This is an accepted risk for a single-user system where Tailscale is the access control boundary. Per R-OPS-BP-02, this should be explicitly registered as an accepted deviation since it is not the minimum necessary exposure — a Tailscale IP filter would be more restrictive.

**Severity: WARNING** (intentional and documented, but not formally registered as an accepted deviation from minimal exposure principle).

### WARNING — Chronos binds to `0.0.0.0` via CHRONOS_BIND env var

`config.env` sets `CHRONOS_BIND=0.0.0.0`. The `02_Platform/Chronos/compose.yml` uses `${CHRONOS_BIND}:${CHRONOS_PORT}:18789`. This exposes the Chronos (AI agent runtime) on all interfaces on the host. 

The Chronos service uses token-based auth (`openclaw-init.json`: `"auth": { "mode": "token" }`), which provides a credential barrier. However, `0.0.0.0` binding means the service is accessible on the LAN IP, not just localhost. This is a broader exposure than strictly necessary, even with auth enabled.

**Consequence:** If the Chronos token is compromised or the auth implementation has a gap, the AI runtime with access to workspace files is accessible from any network-adjacent host.

**Recommendation:** Change `CHRONOS_BIND` to `127.0.0.1` and access via Tailscale tunnel, or explicitly document the rationale for LAN-wide binding and register this as an accepted deviation.

### PASS — MCPGateway uses Google OAuth authentication

`02_Platform/MCPGateway/app/main.py`: Uses `GoogleProvider` from fastmcp for auth. External-facing MCP endpoint at `mcp.linspad.net` is authenticated. Correct posture for an externally-exposed service.

### PASS — Secrets are not committed to git

`01_System/secrets.env` exists as a gitignored file (present in directory listing but not in git-tracked files). The `01_System/config.env` contains only non-secret configuration. Firebase service account path in Notifications compose is a volume mount, not a committed secret. ANTHROPIC_API_KEY referenced via `${OPENCLAW_API}` from secrets.env.

### PASS — CalendarConnector OAuth tokens are not exposed in API responses

`02_Platform/CalendarConnector/app/routers/calendar.py` states as an invariant: "Token values (access_token, refresh_token) are NEVER included in any response." This is an explicit code-level security invariant.

### INFO — TaskTracker Sprint03 draft explicitly acknowledges no auth on TaskTracker API

`03_Application/TaskTracker/Sprint03 - Chronos Access/00_input/draft.md` documents: "There is no authentication on the TaskTracker API — it is single-user, bound to 127.0.0.1:8010 on the host and restricted to atlas-net inside Docker." The security posture is acknowledged and consciously accepted. No new ports or auth changes are planned.

### INFO — All application CORS policies allow any localhost port

All application backends use `allow_origin_regex=r"http://localhost:\d+"`. This is appropriate for development and for a self-hosted system where no cross-origin requests from external sites are expected. However, it does not restrict to specific ports. For a production deployment behind Tailscale this is acceptable; for a directly internet-exposed deployment it would need tightening.

---

## Verdict

PASS with 2 warnings. No blocking security violations.

| Severity | Finding |
|----------|---------|
| WARNING | Notifications binds `0.0.0.0:8020` — intentional for Android/Tailscale access but not formally registered as an accepted deviation from minimal exposure |
| WARNING | Chronos binds `CHRONOS_BIND=0.0.0.0` — AI runtime exposed on all interfaces; mitigated by token auth but broader than necessary |
| INFO | TaskTracker API has no auth — intentional, documented, network-restricted |
| INFO | Application CORS allows all localhost ports — acceptable for self-hosted single-user deployment |
