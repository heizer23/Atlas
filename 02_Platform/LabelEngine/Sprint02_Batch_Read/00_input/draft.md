# LabelEngine Sprint02 — Batch Label Read Endpoint

## Context

LabelEngine currently exposes only a single-object read endpoint:

```
GET /api/objects/{object_id}/labels → ObjectLabelsResponse
```

Applications that render list views (e.g. TaskTracker's `list_tasks`) need labels for many
objects at once. Without a batch endpoint, the only conforming option is N sequential HTTP calls,
which is impractical. This caused TaskTracker to bypass the LabelEngine API entirely and query
the `labels.*` schema directly via SQL — a confirmed platform boundary violation (F-001,
LabelEngine_auditrun_04_09_2026).

## Goal

Add a single batch read endpoint to LabelEngine that allows any application to fetch labels
for a set of objects in one HTTP call. This fixes the root cause of F-001 and unblocks
TaskTracker from removing its direct SQL cross-schema read.

## New endpoint

```
POST /api/objects/labels/batch
```

**Request body:**
```json
{
  "object_ids": ["<uuid>", "<uuid>", ...],
  "object_type": "task"
}
```

**Response:**
```json
{
  "labels": {
    "<object_id>": [
      { "id": "<label_id>", "name": "<label_name>", "attached_at": "<iso8601>" }
    ],
    ...
  }
}
```

- Keys in `labels` are `object_id` strings.
- Value is an array of attached labels ordered by `attached_at ASC`, `label_id ASC` (matching
  the existing per-object ordering from Sprint01).
- Object IDs with no attached labels must appear as empty arrays (zero-fill — not omitted).
- `object_type` is required; behavior is consistent with existing single-object read.
- Maximum `object_ids` per request: 200. Return `422 BATCH_TOO_LARGE` if exceeded.
- Empty `object_ids` list: return `{}` immediately (no DB query).

## Scope

- Add `BatchLabelsRequest` and `BatchLabelsResponse` Pydantic models to `app/models.py`.
- Add `get_labels_for_objects(conn, object_ids, object_type)` to `app/service.py` using a
  single parameterized query (`WHERE ol.object_id = ANY(%s) AND ol.object_type = %s`).
- Add the `POST /api/objects/labels/batch` route to `app/routers/objects.py`.
- Add tests for: happy path (multiple objects), partial hit (some IDs have no labels),
  empty input, over-limit input, and object_type mismatch.

## Out of scope

- Pagination of batch results.
- Filtering by label name within the batch.
- Any changes to existing single-object endpoints.
- Any changes to TaskTracker (that is a separate TaskTracker sprint).

## Consuming application impact

After this sprint, TaskTracker Sprint06 (or equivalent) should replace `fetch_labels_for_tasks`
with a call to this endpoint via `_label_client()`, eliminating the direct SQL cross-schema read.
