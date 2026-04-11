# Sprint02 — LabelEngine Reverse Lookup

## Component
LabelEngine (`02_Platform/LabelEngine`)

## Layer
Platform (`02_Platform`)

## Goal
Add a reverse-lookup endpoint that returns all distinct labels currently attached to at least one object of a given `object_type`. This closes the gap identified in TaskTracker Sprint07: currently there is no way to ask "which labels are in use for tasks?" without owning the join table in the application layer.

## Background
`labels.object_labels` already has an index on `object_type`. The query is a simple distinct join. No schema changes are needed.

## New Endpoint

```
GET /api/labels/used?object_type=<str>
```

- `object_type` is required. Return 422 (`OBJECT_TYPE_REQUIRED`) if absent or blank.
- Returns all distinct labels that have at least one row in `labels.object_labels` for the given `object_type`, ordered by `name` ascending.
- Returns an empty list (not 404) if no labels are attached to any object of that type.
- Response shape: `LabelSearchResponse` — same as `GET /api/labels` — `{ "labels": [{ "id": str, "name": str }] }`.

## Query
```sql
SELECT DISTINCT l.id, l.name
FROM labels.labels l
JOIN labels.object_labels ol ON ol.label_id = l.id
WHERE ol.object_type = $1
ORDER BY l.name
```

## Out of Scope
- Pagination
- Filtering by label name within results
- Any schema changes
