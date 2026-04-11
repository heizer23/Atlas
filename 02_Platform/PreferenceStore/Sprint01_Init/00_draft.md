# Sprint01 — PreferenceStore (Initial Platform Component)

## Component
PreferenceStore (`02_Platform/PreferenceStore`)

## Layer
Platform (`02_Platform`)

## Goal
Build a generic, reusable key-value preference store that any Atlas application or platform component can use to persist user-facing state across page reloads and sessions.

## Motivation
Atlas applications need a shared mechanism to persist UI state (filters, view preferences, display settings) without each application owning its own preference tables. A single platform component provides this capability uniformly, enabling consistent behavior across TaskTracker, Notifications, Chronicle, and any future application.

## Design Constraints
- **Single-user**: no `user_id` dimension for now. If multi-user support is needed in the future, it will be added as a migration.
- **Generic**: the store has no knowledge of what the values mean. Applications own the semantics.
- **Scoped by context**: preferences are addressed by `(scope, key)` where `scope` is a dot-namespaced string owned by the consuming application (e.g. `tasktracker.task-list`).

## Schema

One table in a dedicated `preferences` schema:

```
preferences.preferences
  scope       text        not null   -- e.g. "tasktracker.task-list"
  key         text        not null   -- e.g. "label_filter"
  value_json  jsonb       not null   -- e.g. ["id1", "id2"]
  updated_at  timestamptz not null default now()
  primary key (scope, key)
```

## API Surface

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/preferences/{scope}/{key}` | Retrieve a preference. Returns 404 if not set. |
| PUT    | `/preferences/{scope}/{key}` | Create or overwrite a preference. Body: `{ "value": <any JSON> }`. Returns 200. |
| DELETE | `/preferences/{scope}/{key}` | Remove a preference. Returns 204. |
| GET    | `/preferences/{scope}` | Retrieve all preferences for a scope. Returns `{ "items": [{key, value, updated_at}] }`. |

All read endpoints return a `Dataset` per R-CON-BP-04.

## Behavior
- PUT is upsert (INSERT ... ON CONFLICT DO UPDATE)
- GET on missing key returns 404 with standard `ApiError`
- Scope and key are validated: non-empty, no leading/trailing whitespace
- `value` may be any valid JSON (string, number, array, object, boolean, null)

## Out of Scope
- Authentication or per-user isolation
- Preference schemas or validation (the store is intentionally opaque)
- TTL or expiry
- Audit logging
