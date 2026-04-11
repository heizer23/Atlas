# Atlas Developer Reference

> **Generated** — do not edit manually.
> Last updated: 2026-04-11 18:50 UTC
> Source: `00_architecture/architecture.json` + `compose.yml` per component.
> Regenerated automatically by `/sprint-close`.

This is the primary development reference for Claude Code. Use it to find:
- How to reach any service (host port, container name, URL prefix)
- What endpoints each component exposes
- Caller contracts and gotchas

Components marked ⚠️ have no `00_architecture/` yet — entries are stubs.

---

## 01 System

### Chronos ⚠️

**Summary:** System-level AI gateway (01_System). Handles Telegram, task orchestration, and AI agent dispatch. Not a platform capability consumed by applications.

| | |
|---|---|
| Container | `atlas-chronos` |
| Host port | — |
| Network | atlas-net |
| URL prefix | — |

**Caller notes:**
- Claude Code does not call Chronos. Separate agent world.

### test ⚠️

**Summary:** No 00_architecture yet.

| | |
|---|---|
| Container | — |
| Host port | — |
| Network | atlas-net |
| URL prefix | — |

**Caller notes:**
- Stub — no architecture.json available.

---

## 02 Platform

### Atlas_Shell ⚠️

**Summary:** Nginx-served SPA. Renders Atlas applications via ShellEntry.tsx modules. Not called by other services.

| | |
|---|---|
| Container | `atlas-shell` |
| Host port | `localhost:80` |
| Network | atlas-net |
| URL prefix | — |

**Caller notes:**
- UI runtime only — application backends do not call it.

### CalendarConnector ⚠️

**Summary:** Google Calendar read/write adapter. Handles OAuth, token management, event sync.

| | |
|---|---|
| Container | `atlas-calendar-connector` |
| Host port | `localhost:${CALENDAR_CONNECTOR_PORT:-8021}` |
| Network | atlas-net |
| URL prefix | `/api/calendar` |

**Endpoints:**
```
GET  /api/calendar/events — Dataset of calendar events
GET  /api/calendar/status — Dataset of connection health
GET  /api/calendar/google/connect/start — initiate OAuth
GET  /api/calendar/google/connect/callback — OAuth callback
POST /api/calendar/events — idempotent create event
PATCH /api/calendar/events/{atlas_event_id} — update event
DELETE /api/calendar/events/{atlas_event_id} — delete event
```

**Caller notes:**
- Write target calendar set via CALENDAR_TARGET_CALENDAR_ID env var.
- atlas_event_id is the stable cross-system key — supply on create.
- Token values are never included in responses.

### LabelEngine

**Summary:** Generic label management service that creates labels, attaches and detaches them from application objects by type-scoped string identity, and exposes search, reverse-lookup, batch-read, and grouped-object query capabilities to any Atlas application.

| | |
|---|---|
| Container | `atlas-label-engine` |
| Host port | `localhost:8050` |
| Network | atlas-net |
| URL prefix | `/api` |

**Endpoints:**
```
GET /api/labels?q=<prefix> — case-insensitive prefix label search; empty q returns all labels ordered by name ASC
GET /api/labels/used?object_type=<str> — all distinct labels attached to at least one object of the given type, ordered by name ASC
POST /api/labels — create a named label; returns 201 LabelRecord
GET /api/objects/{object_id}/labels — all labels attached to an object, ordered by attached_at ASC then label_id ASC
POST /api/objects/{object_id}/labels — attach a label to an object by name; creates the label inline if not found; idempotent
DELETE /api/objects/{object_id}/labels/{label_id} — detach a label from an object; returns 204
POST /api/objects/labels/batch — return labels for up to 200 objects in one call, scoped by object_type; zero-fills missing entries
GET /api/groups?object_type=<str>&page=<int>&page_size=<int> — objects of a type grouped by primary label, paginated; named groups alphabetically then Unlabeled last
GET /health — liveness check, returns {status: ok}
```

### LinkingEngine ⚠️

**Summary:** Generic cross-object relationship store. Any two registered objects can be linked with a named relation.

| | |
|---|---|
| Container | `atlas-linking-engine` |
| Host port | `localhost:8040` |
| Network | atlas-net |
| URL prefix | `/linking` |

**Endpoints:**
```
POST   /linking/objects — register or update an object
GET    /linking/objects/search — fuzzy search by type and q
POST   /linking/links — create a link between two objects
DELETE /linking/links/{link_id} — soft-delete a link
GET    /linking/links — raw link query
GET    /linking/objects/{object_id}/links — grouped links for an object
```

**Caller notes:**
- Objects must be registered before linking.
- GET /linking/objects/{id}/links returns grouped shape — not a Dataset. Backends must transform before serving the UI.
- Deletion is soft (archived_at). No hard-delete endpoint.

### MCPGateway ⚠️

**Summary:** MCP protocol gateway exposing Atlas tools to external AI clients (e.g. ChatGPT). Not consumed by Atlas applications.

| | |
|---|---|
| Container | `atlas-mcp-server` |
| Host port | `localhost:8002` |
| Network | host (network_mode: host) |
| URL prefix | — |

**Caller notes:**
- Not for inter-application calls within Atlas.
- Uses host network mode — reaches Postgres and other services via 127.0.0.1.

### Notifications ⚠️

**Summary:** Push notification scheduling and FCM dispatch. Application backends enqueue notifications here.

| | |
|---|---|
| Container | `atlas-notifications` |
| Host port | `localhost:8020` |
| Network | 0.0.0.0 (LAN-accessible via Tailscale for Android) |
| URL prefix | `/api/notifications` |

**Endpoints:**
```
POST   /api/notifications/ — enqueue a notification
DELETE /api/notifications/{id} — cancel a pending notification
POST   /api/notifications/{id}/replace — cancel + recreate atomically (best-effort)
POST   /api/devices/token — register or update FCM token
GET    /api/devices/token — retrieve current FCM token
```

**Caller notes:**
- Notifications are enqueued, not dispatched synchronously (default 30s interval).
- replace is not atomic — old cancelled first, then new created.
- device_id = 'default' is the single-device MVP convention.

### PreferenceStore

**Summary:** Generic key-value store keyed by (scope, key) that any Atlas application can use to persist user-facing UI state across page reloads and sessions.

| | |
|---|---|
| Container | `atlas-preference-store` |
| Host port | `localhost:8060` |
| Network | atlas-net |
| URL prefix | `/api` |

**Endpoints:**
```
GET /preferences/{scope}/{key} — retrieve one preference or 404
PUT /preferences/{scope}/{key} — upsert a preference, returns 200
DELETE /preferences/{scope}/{key} — remove a preference, returns 204
GET /preferences/{scope} — retrieve all preferences for a scope as Dataset
GET /health — liveness check, returns {status: ok}
```

---

## 03 Application

### Chronicle ⚠️

**Summary:** Append-only log / journal application. Stores timestamped entries.

| | |
|---|---|
| Container | `atlas-chronicle` |
| Host port | `localhost:8013` |
| Network | atlas-net |
| URL prefix | `/api` |

**Caller notes:**
- No 00_architecture yet — stub only.

### FoodTracker ⚠️

**Summary:** Food and nutrition tracking application.

| | |
|---|---|
| Container | `atlas-food-tracker` |
| Host port | `localhost:8012` |
| Network | atlas-net |
| URL prefix | `/api` |

**Caller notes:**
- No 00_architecture yet — stub only.

### NumericSeries ⚠️

**Summary:** Generic numeric time-series tracking application.

| | |
|---|---|
| Container | `atlas-numeric-series` |
| Host port | `localhost:8014` |
| Network | atlas-net |
| URL prefix | `/api` |

**Caller notes:**
- No 00_architecture yet — stub only.

### StorageTracker

**Summary:** Household item tracking application. Users create and maintain items categorised as consumable, object, or pending_action. Items have a lifecycle state (stored, low_stock, out_of_stock, marked_for_recycling, missing, lent_out), a free-text location, and optional quantity tracking for consumables. State changes and location changes are recorded in an append-only history table.

| | |
|---|---|
| Container | `atlas-storagetracker` |
| Host port | `localhost:8022` |
| Network | atlas-net |
| URL prefix | `/api` |

**Endpoints:**
```
GET /api/items — list all items; params: state (stored|low_stock|out_of_stock|marked_for_recycling|missing|lent_out), item_type (consumable|object|pending_action), location (exact match string), source_tag (string — matches any element of source_tags array); default ordering: created_at DESC; returns Dataset
POST /api/items — create item; body: {name, item_type, location?, notes?, source_tags?: list[str], quantity?: int, min_quantity?: int, state? (default stored)}; auto-transitions state to low_stock if quantity and min_quantity are both set and quantity <= min_quantity; records history entry with change_type=created; returns Dataset (single row)
GET /api/items/{id} — get single item with last 20 history entries; returns Dataset (single row with embedded history)
PATCH /api/items/{id} — partial update; body: any subset of {name, state, location, quantity, min_quantity, notes, source_tags}; field omission means no change; explicit null clears nullable fields; after any quantity or min_quantity change, auto-recomputes state to low_stock if both are set and quantity <= min_quantity (unless caller explicitly set state); records history entries for each changed field; returns Dataset (single row)
DELETE /api/items/{id} — delete item and its history; returns empty Dataset on success, 404 ApiError if not found
GET /api/items/{id}/history — full history for item ordered by timestamp DESC; returns Dataset
GET /api/items/views/low_stock — items where state is low_stock or out_of_stock; ordered by name ASC; returns Dataset
GET /api/items/views/recycling — items where state is marked_for_recycling; ordered by name ASC; returns Dataset
GET /api/items/views/important — items where item_type is object; ordered by name ASC; returns Dataset
GET /api/items/views/search?q=<text> — case-insensitive substring search across name, location, notes; returns Dataset ordered by name ASC; empty q returns empty Dataset
```

### TaskTracker

**Summary:** Lightweight single-user task management application that creates, tracks, and labels tasks with status, priority, due date, and effort fields, persisting tasks in Postgres and delegating label management to LabelEngine and user preferences to PreferenceStore.

| | |
|---|---|
| Container | `atlas-tasktracker` |
| Host port | `localhost:8010` |
| Network | atlas-net |
| URL prefix | `/api` |

**Endpoints:**
```
GET /api/tasks — list tasks; params: status (open|in_progress|pending|done), view (active|pending_board), page (default 1), page_size (default 25); returns Dataset with labels embedded per row
POST /api/tasks — create a task; body: {title, description?, status? (open|pending, default open), priority? (low|medium|high, default medium), due_date?, effort_hours?}; returns Dataset (single row)
PATCH /api/tasks/{task_id} — partial update; body: any subset of {title, description, status, priority, due_date, effort_hours}; field omission means no change; explicit null clears nullable fields; returns Dataset (single row)
DELETE /api/tasks/{task_id} — delete task; returns empty Dataset on success, 404 ApiError if not found
GET /api/tasks/labels/search — search labels by prefix via LabelEngine; param: q (default empty string); returns Dataset {object_type: label, rows: [{id, name}]}
GET /api/tasks/labels/used — all labels attached to at least one task via LabelEngine; returns Dataset {object_type: label, rows: [{id, name}]}; empty Dataset on LabelEngine failure
GET /api/tasks/{task_id}/labels — labels on one task via LabelEngine; returns Dataset {object_type: task_label, rows: [{id, name, attached_at}]}
POST /api/tasks/{task_id}/labels — attach a label by name; body: {label_name: str}; proxies LabelEngine; returns LabelEngine response
DELETE /api/tasks/{task_id}/labels/{label_id} — detach a label from a task; proxies LabelEngine; returns 204 or ApiError
PUT /api/tasks/{task_id}/labels — atomically replace all labels on a task with the provided list; body: {labels: list[str]}; fetches current, detaches all, attaches new set; returns updated label list
GET /api/tasks/preferences/label_filter — retrieve stored label filter selection from PreferenceStore; returns Dataset (one row) or 404 ApiError if not yet saved
PUT /api/tasks/preferences/label_filter — persist label filter selection; body: {label_ids: list[str]}; stores to PreferenceStore; returns 200 PreferenceRecord or ApiError
```

### WorkoutTracker ⚠️

**Summary:** Workout and exercise tracking application.

| | |
|---|---|
| Container | `atlas-workout-tracker` |
| Host port | `localhost:8011` |
| Network | atlas-net |
| URL prefix | `/api` |

**Caller notes:**
- No 00_architecture yet — stub only.
