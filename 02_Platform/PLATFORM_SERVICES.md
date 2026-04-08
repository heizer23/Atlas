# Platform Services Index

> **Audience:** Application designers, application implementers, and orchestration agents.
> **Purpose:** Authoritative index of available platform HTTP services. Read this before designing any application feature that requires cross-object linking, labelling, calendar access, or push notification dispatch.
> **Maintenance:** Update this file when a new platform service is added, a port changes, or a contract-level invariant is confirmed or changed. This is a governance artifact — do not update it as a side-effect of implementation work without explicit intent.

---

## Port Registry

| Service | Port (host) | Container | Status |
|---|---|---|---|
| Notifications | `8020` | `atlas-notifications` | Active |
| CalendarConnector | `8021` (env: `CALENDAR_CONNECTOR_PORT`) | `atlas-calendar-connector` | Active |
| MCPGateway | `8002` | `atlas-mcp-server` | Active |
| LinkingEngine | `8040` | `atlas-linking-engine` | Active |
| LabelEngine | `8050` | `atlas-label-engine` | Active |

All services run on `atlas-net` (Docker external network). All except MCPGateway and Notifications bind to `127.0.0.1` only. Notifications binds `0.0.0.0` to allow Android device access via Tailscale.

---

## Infrastructure (non-HTTP)

### Shared Postgres (`02_Platform/01_Postgres`)

Shared database instance used by all platform services. Not called directly via HTTP. Access is via `ATLAS_PG_*` environment variables. Each service owns its own schema namespace inside the shared instance (e.g. `labels`, `linking`, `notifications`). Cross-schema SQL joins are forbidden — services must call each other via HTTP.

### Platform Packages (`02_Platform/packages/`)

Python library packages copied into service images at build time. Not deployed as a service.

| Package | Purpose |
|---|---|
| `platform_contracts` | Canonical `Dataset`, `DatasetMeta`, `ColumnSchema`, `ApiError` types |
| `platform_errorhandling` | Structured logging, `api_error()` helper, FastAPI exception handler installation |

Application backends import from these packages directly (not via HTTP).

---

## HTTP Services

### LinkingEngine — `02_Platform/LinkingEngine`

**Port:** `127.0.0.1:8040`
**Purpose:** Generic cross-object relationship store. Allows any two registered objects to be linked with a named relation. No domain meaning is encoded here — meaning lives in relation definitions.

#### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/linking/objects` | Register or update an object in the linking registry (204) |
| `GET` | `/linking/objects/search` | Fuzzy title search by `type` and `q` |
| `POST` | `/linking/links` | Create a link between two registered objects |
| `DELETE` | `/linking/links/{link_id}` | Soft-delete (archive) a link |
| `GET` | `/linking/links` | Raw link query (filter by `from_object_id`, `to_object_id`, `relation_key`) |
| `GET` | `/linking/objects/{object_id}/links` | Grouped, display-ready links for a given object |

#### Key contracts for callers

- **Objects must be registered before linking.** Call `POST /linking/objects` on entity creation and on title updates. Linking an unregistered object produces `OBJECT_NOT_FOUND`.
- **Relation input is free-text, normalized server-side.** The canonical relation keys live in the `relation_definitions` table. Callers do not need to know them; the service resolves them.
- `GET /linking/objects/{object_id}/links` returns `{ object_id, groups: [LinkGroup] }` — **not a Dataset**. Application backends must transform this into a Dataset before serving the Atlas Shell UI.
- Deletion is soft (sets `archived_at`). There is no hard-delete endpoint.

#### Shared response types

```
ObjectRecord:          { object_id, workspace_id?, type, title? }
LinkRecord:            { link_id, from_object_id, to_object_id, relation_key, created_by_type, created_by_id?, confidence, archived_at?, created_at }
RelationDefinition:    { key, forward_label, reverse_label, is_directional, allowed_from_types, allowed_to_types, is_active, sort_order }
LinkGroup:             { group_key, label, items: [{ object_id, type, title? }] }
```

---

### LabelEngine — `02_Platform/LabelEngine`

**Port:** `127.0.0.1:8050`
**Purpose:** Generic many-to-many label store. Any object-bearing application can attach, remove, search, and group objects by named labels. No domain meaning is encoded here.

#### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/labels` | Search labels by name prefix (`q` param, optional — empty returns all) |
| `POST` | `/api/labels` | Create a named label. Returns `LabelRecord`. |
| `POST` | `/api/objects/{object_id}/labels` | Attach a label to an object by name. Creates label inline if absent. Idempotent. |
| `DELETE` | `/api/objects/{object_id}/labels/{label_id}` | Remove a specific label from a specific object |
| `GET` | `/api/objects/{object_id}/labels` | All labels on a given object, ordered by `attached_at` ascending |
| `GET` | `/api/groups` | Objects grouped by primary label, scoped by `object_type` (required param) |

#### Key contracts for callers

- **LabelEngine does not validate object existence.** Callers must pre-check that the object exists before attaching labels. Orphaned attachments (labels on deleted objects) persist until the caller cleans them up. No cascade-delete exists yet.
- **Primary label = first label attached** (`MIN(attached_at)`, ties broken by `label_id ASC`). Any display or sort by primary label depends on this rule. Do not batch multiple label attaches in a single transaction if insertion order matters for UX.
- **`GET /api/groups` returns `GroupedObjectsResponse` — not a Dataset.** The Atlas Shell UI cannot call LabelEngine directly. Application backends must proxy all label operations and transform responses into Dataset shape before serving the UI (R-CON-BP-04).
- **`object_type` is a caller-defined string.** Pick a stable value per entity type (e.g. `"task"`) and use it consistently across all attach and group calls. There is no central registry of valid values.
- Label names are case-insensitively matched on attach (leading/trailing whitespace stripped). `"Outside"` and `"outside"` resolve to the same label.

#### Shared response types

```
LabelRecord:              { id: str, name: str }
ObjectLabelRecord:        { object_id, label_id, label_name, attached_at (ISO-8601) }
LabelSearchResponse:      { labels: [LabelRecord] }
ObjectLabelsResponse:     { labels: [ObjectLabelRecord] }
GroupedObjectsResponse:   { groups: [{ label: str | "Unlabeled", items: [{ id, primary_label, labels }] }] }
```

#### Error codes

| Code | Status | Meaning |
|---|---|---|
| `LABEL_NAME_EMPTY` | 422 | Label name is blank after stripping whitespace |
| `LABEL_NOT_FOUND` | 404 | `label_id` does not exist |
| `ATTACHMENT_NOT_FOUND` | 404 | `(object_id, label_id)` pair does not exist |
| `OBJECT_TYPE_REQUIRED` | 422 | `GET /api/groups` called without `object_type` |
| `DB_UNAVAILABLE` | 503 | Postgres unreachable or pool exhausted |

---

### CalendarConnector — `02_Platform/CalendarConnector`

**Port:** `${CALENDAR_CONNECTOR_PORT:-8021}` (env-configured; default 8021)
**Purpose:** Google Calendar read/write adapter. Handles OAuth, token management, event sync, and write-back. Exposes Dataset-shaped read endpoints and structured write endpoints.

#### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/calendar/google/connect/start` | Initiate Google OAuth consent flow |
| `GET` | `/api/calendar/google/connect/callback` | OAuth callback — exchange code for tokens |
| `GET` | `/api/calendar/events` | Dataset of calendar events (read) |
| `GET` | `/api/calendar/status` | Dataset of connection health (singleton row, `id = "system"`) |
| `POST` | `/api/calendar/events` | Idempotent create event. Returns `CalendarEventOperationResult`. |
| `PATCH` | `/api/calendar/events/{atlas_event_id}` | Update existing event. Returns `CalendarEventOperationResult`. |
| `DELETE` | `/api/calendar/events/{atlas_event_id}` | Idempotent delete event. Returns `CalendarDeleteResult`. |

#### Key contracts for callers

- **Write target calendar is operator-configured** (`CALENDAR_TARGET_CALENDAR_ID` env var). Callers cannot specify a destination calendar — there is no `calendar_id` field in write request bodies.
- **`atlas_event_id` is the stable cross-system key.** Callers must supply it on create; it is used for idempotency and for subsequent update/delete. The Google event ID is internal.
- `POST` returns `201` on `status='created'`, `200` on `status='existing'` (idempotent repeat).
- Token values (`access_token`, `refresh_token`) are never included in any response.
- `GET /api/calendar/events` and `GET /api/calendar/status` return `Dataset` — these are UI-safe endpoints.
- Write endpoints return typed JSON payloads (`CalendarEventOperationResult`, `CalendarDeleteResult`) — not Datasets. Application backends must wrap these if the result needs to reach the UI.

---

### Notifications — `02_Platform/Notifications`

**Port:** `0.0.0.0:8020` (accessible on network for Android via Tailscale)
**Purpose:** Push notification scheduling and FCM dispatch. Application backends enqueue notifications here; a scheduler dispatches them via Firebase Cloud Messaging.

#### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/notifications/` | Create (enqueue) a notification. Returns `NotificationRecord` (201). |
| `DELETE` | `/api/notifications/{id}` | Cancel a pending notification |
| `POST` | `/api/notifications/{id}/replace` | Cancel old + create new notification atomically (best-effort) |
| `POST` | `/api/devices/token` | Register or update FCM token for a device |
| `GET` | `/api/devices/token` | Retrieve current FCM token for a device |

#### Key contracts for callers

- Notifications are enqueued, not dispatched synchronously. Dispatch happens on the scheduler interval (default 30s, env `NOTIFICATIONS_DISPATCH_INTERVAL_SECONDS`).
- `replace` is not atomic — old notification is cancelled first, then new is created. A failure between the two steps can leave neither active.
- `device_id = "default"` is the single-device MVP convention.

---

### MCPGateway — `02_Platform/MCPGateway`

**Port:** `8002` (host network mode)
**Purpose:** MCP protocol gateway exposing Atlas application tools to external AI clients (e.g. ChatGPT). Authenticated via Google OAuth. Not consumed by Atlas applications — this is an outbound interface for external AI access.

#### Key contracts

- Application tools are registered in `app/main.py` as plain Python functions. Each new application that wants to expose tools to external AI must register them here.
- Uses `network_mode: host` — it reaches Postgres and other services via `127.0.0.1`.
- This service is **not** for inter-application calls within Atlas. Do not call it from application backends.

---

## Adding a New Platform Service

When a new HTTP platform service is deployed:

1. Assign a host port not already listed in the Port Registry above.
2. Add the service to the Port Registry table.
3. Add a service entry in this file covering: purpose, all endpoints, key caller contracts, and shared response types.
4. Regenerate the system map: `python .claude/tools/generate_atlas_system_map.py /home/linse/Prod/Atlas`
