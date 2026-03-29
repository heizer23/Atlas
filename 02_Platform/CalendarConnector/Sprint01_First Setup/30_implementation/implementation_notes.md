# CalendarConnector — Sprint 01 Implementation Notes

## What was implemented

### Application files
- `app/main.py` — FastAPI app, CORS with `allow_origin_regex`, platform error handlers, startup hook
- `app/database.py` — psycopg2 pool, `init_pool()`, `get_db()`, `init_schema()` that runs `migrations/001_init.sql`
- `app/models.py` — `CalendarEventRow` and `CalendarConnectionStatusRow` Pydantic models (shared_views types)
- `app/routers/calendar.py` — all four endpoints per `internal_flow` in architecture.json
- `app/services/google_oauth.py` — `build_authorization_url()`, `exchange_code_for_tokens()`, `refresh_access_token()`, `get_account_email()` using httpx
- `app/services/calendar_api.py` — `fetch_events()` calling Google Calendar API v3 events.list, normalizes to `CalendarEventRow`
- `app/services/token_store.py` — all DB reads/writes: `get_connection()`, `upsert_connection()`, `update_connection_status()`, `record_success()`, `get_token()`, `upsert_token()`, `create_oauth_state()`, `consume_oauth_state()`
- `migrations/001_init.sql` — idempotent schema creation for `calendar_connection`, `calendar_token`, `calendar_oauth_state`
- `Dockerfile` — follows TaskTracker pattern; copies platform packages to `/platform_packages`, sets `PYTHONPATH`
- `compose.yml` — `atlas-calendar-connector` service on `${CALENDAR_CONNECTOR_PORT:-8021}:8000`
- `pyproject.toml` — declares httpx as a new dependency (not in TaskTracker's pyproject.toml)
- `tests/` — stub files for test_writer (no implementation this sprint per scope)

### nginx.conf update
Added `/api/calendar` location block to `02_Platform/02_Atlas_Shell/nginx.conf` with upstream `atlas-calendar-connector:8000`. Follows the exact pattern of existing service blocks.

### config.env
`CALENDAR_CONNECTOR_PORT=8021` was already registered in `01_System/config.env` (present before this implementation sprint).

---

## Implementer decisions

### Account email extraction
Used Google userinfo endpoint (`https://www.googleapis.com/oauth2/v3/userinfo`) rather than decoding `id_token`. This avoids adding a JWT library dependency. The access_token obtained during the initial exchange is used for the userinfo call immediately after token exchange.

### Token refresh trigger
Lazy refresh on every `GET /api/calendar/events` request that finds `token_expiry <= now`. No background worker. Consistent with the architecture.json recommendation for this slice.

### CSRF state storage
DB nonce row in `calendar_oauth_state` with `expires_at` (10-minute TTL). Nonce is deleted (consumed) on first use in `connect_callback`. This is the approach recommended in architecture.json.

### OAuth callback URI configuration
The callback URI defaults to `http://localhost:{CALENDAR_CONNECTOR_PORT}/api/calendar/google/connect/callback`. It can be overridden via the `CALENDAR_CALLBACK_URI` environment variable for non-local deployments. This avoids hardcoding the port in two places.

### Dataset construction
The `schema` field uses the `**{"schema": [...]}` unpacking pattern because `schema_` is the Python alias for the Pydantic field with `alias="schema"`.

---

## Known security gap: token plaintext storage

**Status: known gap, deferred**

`access_token` and `refresh_token` are stored as plaintext TEXT columns in the `calendar_token` table. Any user with Postgres read access (`atlas` user, DB admin, or any compromised service with DB credentials) can extract live Google Calendar OAuth credentials.

**Impact:** read access to the connected Google Calendar account.

**Required before production use:** encrypt token fields at rest (application-level encryption with a key from secrets.env, or use Postgres `pgcrypto`).

This gap is documented in `architecture.json` risks and `migrations/001_init.sql` comments.

---

## Deployment pre-condition: Google Cloud Console callback URI

Before end-to-end testing, register the following URI as an **Authorized redirect URI** in Google Cloud Console for the existing OAuth client (`GOOGLE_CLIENT_ID`):

```
http://localhost:8021/api/calendar/google/connect/callback
```

Steps:
1. Go to [Google Cloud Console](https://console.cloud.google.com/) > APIs & Services > Credentials
2. Select the existing OAuth 2.0 Client ID used by Atlas (same `GOOGLE_CLIENT_ID` from `config.env`)
3. Add `http://localhost:8021/api/calendar/google/connect/callback` to Authorized redirect URIs
4. Save

If this URI is not registered, every attempt to connect will fail at Google's authorization endpoint with `redirect_uri_mismatch`. This is a deployment pre-condition, not a code defect.

For production, register the HTTPS variant (e.g. `https://atlas.yourdomain.com/api/calendar/google/connect/callback`) and set `CALENDAR_CALLBACK_URI` accordingly in the deployment environment.

---

## httpx dependency

httpx was confirmed present in the MCPGateway component but was not in `TaskTracker/pyproject.toml`. It is added to `CalendarConnector/pyproject.toml` as an explicit dependency (`httpx>=0.27`). It is used by both `google_oauth.py` and `calendar_api.py`.

---

## What remains out of scope (this slice)

- Writing events to Google Calendar
- Background sync workers
- Webhook push notifications
- Multi-user / per-user connections (Atlas is system-scoped: one connection per instance)
- At-rest token encryption
- UI (no frontend work this sprint)
- Tests (stubs created, implementation deferred to test_writer)
- Extension of `migrate.py` to cover Platform paths (architecture.json design_decisions)

---

## Open questions resolved

1. **Account email extraction method** — resolved: userinfo endpoint (no JWT library).
2. **httpx availability** — resolved: added to pyproject.toml explicitly.
