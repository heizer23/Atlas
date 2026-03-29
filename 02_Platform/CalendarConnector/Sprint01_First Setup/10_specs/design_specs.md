# Design Specs — CalendarConnector Sprint01_First Setup

**Verdict: READY**

The spec is ready for designer handoff. All critical product decisions are defined, Atlas alignment is sound, and the two orchestrator-flagged quality issues have been resolved below. Remaining open areas are safe designer decisions.

---

## Verdict
READY

---

## Orchestrator Flag Resolution

### Flag 1 — Callback URI ambiguity
Resolved by codebase search.

The draft states `http://localhost:8000/auth/google/callback` as the current local development redirect URI. A full search of the repository found no existing web-based Google OAuth flow with this or any similar route. The only existing Google OAuth usage is in `02_Platform/MCPGateway/app/main.py`, which uses FastMCP's `GoogleProvider` — an MCP-protocol auth mechanism, not a web redirect flow. That flow uses `MCP_BASE_URL=https://mcp.linspad.net` and has no `/auth/google/callback` route.

**Decision recorded:** `http://localhost:8000/auth/google/callback` is a new URI. It does not conflict with any existing route. The designer must register this URI in the Google Cloud Console for the existing OAuth client (`GOOGLE_CLIENT_ID` from `config.env`) as a new authorized redirect URI for local development. The production URI will be `https://<atlas-domain>/calendar/google/connect/callback` or equivalent — this must be confirmed before production deployment but is explicitly out of scope for this slice.

**Designer action required:** The callback handler endpoint must be registered in the Google Cloud Console under the existing OAuth client before the OAuth flow can be tested end-to-end. This is a deployment pre-condition, not an implementation decision.

### Flag 2 — Single-user vs multi-user
Resolved by codebase inspection and draft intent.

Inspection of all application backends confirms Atlas is currently a single-user system. No application (`TaskTracker`, `WorkoutTracker`, `FoodTracker`, `Chronicle`) has a `user_id` column or any authentication middleware. There is no user identity model in the platform.

**Decision recorded:** For this slice, `calendar_connection` and `calendar_token` do NOT require a `user_id` foreign key. The connection is system-scoped (one calendar connection per Atlas instance). This is consistent with the rest of Atlas. If Atlas ever becomes multi-user, a migration adding `user_id` to these tables will be required — that is an explicitly deferred concern. The designer must NOT add a `user_id` FK.

---

## Must-Fix Issues (Blocking)
None.

---

## Safe-to-Defer Decisions (Designer can handle)

**DB table layout (one vs two tables)**
The draft permits collapsing `calendar_connection` and `calendar_token` into one table if Atlas conventions prefer it. Either is acceptable as long as all required state fields are present and explicit. The designer decides.

**CSRF state parameter implementation**
The draft requires CSRF protection on the OAuth flow and mentions "state handling appropriate for CSRF protection." The specific mechanism (signed JWT, encrypted session cookie, short-lived nonce stored in DB, Redis-backed nonce) is a designer decision. Any standard OAuth state parameter approach is acceptable. The designer chooses.

**`/calendar/status` response shape**
The draft marks this endpoint as "optional but recommended." The designer decides whether to include it and what fields to expose (subject to the constraint: no secrets in response). If included, the response should be a `Dataset` per the UI Data Contract, with an `object_type` of `calendar_connection_status` or equivalent.

**Event normalization field optionality**
The draft lists minimum fields for the normalized event shape. `description`, `location`, `source_calendar_label`, and `last_error` are implicitly optional (not always present in Google Calendar API responses). The designer decides which fields are nullable vs required in the internal model.

**Endpoint prefix and router placement**
The draft suggests `/calendar/google/connect/start`, `/calendar/google/connect/callback`, `/calendar/events`. The designer may adapt the prefix to match the Atlas service routing convention (e.g., `/api/calendar/...` if the component is proxied through the Atlas Shell nginx, or bare `/calendar/...` if it runs as a standalone service like the other platform components). See Atlas context below.

**Internal token refresh strategy**
The draft does not specify when token refresh happens — on every events request that finds an expired token, or proactively. Either is acceptable. The designer decides.

---

## Atlas Violations / Redundancies

**Potential routing mismatch — endpoint prefix**
The draft specifies `/calendar/google/connect/start` and `/calendar/events` without an `/api/` prefix. Atlas application backends use the `/api/` prefix (e.g., `/api/tasks`, `/api/workout`), and the nginx proxy routes by prefix. If CalendarConnector is deployed as a standalone service proxied through the Atlas Shell, the nginx config (`02_Platform/02_Atlas_Shell/nginx.conf`) will need a new `location /api/calendar` block. The designer must decide whether to use the `/api/` prefix convention or justify a deviation.

**`/calendar/events` response must be a `Dataset`**
The draft says "returns a normalized response" for the events endpoint without specifying it must be a `Dataset`. Per R-CON-BP-04, any Atlas endpoint that surfaces data through the Atlas UI must return a `Dataset`. If this endpoint is ever consumed by a UI component, it must return `Dataset`. The designer must use `Dataset` for this endpoint — not an ad hoc list of events.

Mapping:
- `meta.object_type`: `"calendar_event"`
- `meta.label`: `"Calendar Events"`
- `meta.total`: total event count in the window
- `schema`: keys matching the normalized event fields (id, title, start_at, end_at, all_day, etc.) with appropriate `ColumnType` per R-CON-BP-04 §1.1
- `rows`: each row must have an `id` field (can be `external_event_id` if unique, or a surrogate)
- `row_actions`: `[]` (read-only in this slice)

**Error responses must use `api_error()` from `platform_errorhandling`**
The draft references Atlas error conventions. The canonical helper is `api_error(code, message, detail, status)` from `02_Platform/packages/platform_errorhandling/api_response.py`. The designer must not invent a different error shape. This is already aligned in the draft; recorded here for the designer's explicit reference.

**`/calendar/status` response — if included, must be `Dataset`**
Same rule as above. The status endpoint must return a `Dataset` if it surfaces data to any UI. `object_type: "calendar_connection"` is appropriate.

---

## Ambiguities with Suggested Resolution

**Where does CalendarConnector run as a service?**
The draft does not specify whether CalendarConnector is a new standalone FastAPI service (like Chronicle at port 8013) or is embedded in an existing service. Every other Atlas platform/application component runs as its own service.
Recommended decision: new standalone FastAPI service with its own port, following the pattern of existing components (e.g., `chronicle`, `notifications`). Add an `atlas-calendar-connector` entry to the service roster and a new nginx proxy route. Confidence: High.

**Which port should CalendarConnector use?**
Not specified. `config.env` shows ports 8010–8013 for applications and 8020 for Notifications. Next available platform port would be 8021 or a new block.
Recommended decision: assign port 8021 for CalendarConnector; record in `config.env`. Confidence: Medium (port assignment is operational, not architectural — any unused port is acceptable).

**OAuth callback URI path**
The draft shows `/auth/google/callback` as the callback path (not `/calendar/google/connect/callback`). This looks like a placeholder that was copied from a generic OAuth example rather than the intended component-namespaced path.
Recommended decision: use `/calendar/google/connect/callback` (consistent with the start endpoint at `/calendar/google/connect/start`). The Google Cloud Console authorized redirect URI must match whatever path is chosen. Confidence: High — the `/auth/google/callback` path conflicts with the naming intent of the spec.

**Token storage — encrypt at rest or store plaintext?**
The draft says "sensitive fields must not be exposed in API responses" but does not mention encryption at rest for `access_token` and `refresh_token`.
Recommended decision: store tokens as plaintext in the database for this slice (consistent with Atlas's current approach across all applications — no at-rest encryption layer exists). Flag as a known security gap in implementation notes. Confidence: High.

---

## Risks

**Callback URI registration gap — High**
If the Google Cloud Console redirect URI is not updated to include the new callback URL before testing, the OAuth flow will fail at Google's side with `redirect_uri_mismatch`. This is a deployment pre-condition that cannot be tested without it. The designer should include an explicit note in the implementation deliverables that this registration step is required.

**`Dataset` contract for events endpoint — Medium**
If the implementer produces an ad hoc JSON list instead of a `Dataset`, any future UI consumption will require a breaking change to the endpoint. The spec must be clear that `Dataset` is required.

**Login isolation drift — Medium**
The draft is explicit about login isolation. However, if the designer places the CalendarConnector's callback route under `/auth/...` (matching the draft's literal `http://localhost:8000/auth/google/callback`), it creates a naming proximity to login that risks confusing future agents. Keeping all calendar routes under `/calendar/...` eliminates this risk.

**MCPGateway auth scope collision — Low**
MCPGateway uses the same `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` for MCP protocol auth. The OAuth scopes requested by CalendarConnector (`calendar.readonly`) are different from the scopes used by MCPGateway (identity/OpenID). These are separate consent flows and separate tokens — no collision — but the designer should note in the architecture document that both components share credentials but maintain independent token state.

**Over-normalization of event shape — Low**
The draft warns against over-designing a universal calendar abstraction. Risk is low given the explicit constraint, but the designer should resist adding provider-agnostic abstraction layers (e.g., a `CalendarProvider` interface) until a second provider is actually required.

---

## Minimal Edits to Reach READY
Not applicable — verdict is READY.

---

## Authoritative Context for Designer

**Existing Google OAuth usage**
File: `02_Platform/MCPGateway/app/main.py`
Uses: FastMCP `GoogleProvider` for MCP protocol auth (ChatGPT → Atlas MCP Gateway). Not a web redirect flow. No `/auth/google/callback` route exists. Shares `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from environment. CalendarConnector must reuse these same credentials without modifying this file.

**Credentials location**
- `GOOGLE_CLIENT_ID` — `01_System/config.env` (public, committed)
- `GOOGLE_CLIENT_SECRET` — `01_System/secrets.env` (gitignored)
- Add `CALENDAR_CONNECTOR_PORT` and any new config keys to `config.env`

**Atlas service pattern**
Every backend service follows the pattern in `03_Application/TaskTracker/backend/main.py`:
- FastAPI app
- `CORSMiddleware` with `allow_origin_regex`
- `install_exception_handlers(app)` from `platform_errorhandling`
- `install_request_timing(app)` from `platform_errorhandling`
- Router mounted with prefix
- `on_event("startup")` for DB pool and schema init

**Error helper**
`api_error(code, message, detail, status)` from `02_Platform/packages/platform_errorhandling/api_response.py`

**Dataset types**
Import from `02_Platform/packages/platform_contracts/contracts.py` — never redefine locally.

**DB migration pattern**
Follow `02_Platform/01_Postgres/migrate.py` for migration conventions.

**Nginx proxy**
Add a `location /api/calendar` block to `02_Platform/02_Atlas_Shell/nginx.conf` following the existing pattern.

---

## Summary of Resolved Decisions

| Decision | Resolution |
|---|---|
| Callback URI conflicts with existing route? | No conflict. URI is new. Register in Google Cloud Console. |
| Single-user or multi-user DB schema? | Single-user (system-scoped). No `user_id` FK. |
| `calendar_connection.user_id` FK required? | No. |
| Events endpoint response shape | `Dataset` per R-CON-BP-04 |
| Error response shape | `api_error()` from `platform_errorhandling` |
| Callback path | `/calendar/google/connect/callback` (not `/auth/google/callback`) |
| Token storage encryption | Plaintext for this slice; flag as known gap |
| Service deployment pattern | Standalone FastAPI service, new port |
