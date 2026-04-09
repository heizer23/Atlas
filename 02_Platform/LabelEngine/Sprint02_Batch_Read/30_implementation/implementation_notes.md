# Implementation Notes — LabelEngine Sprint02_Batch_Read

## What was implemented

### `app/models.py`
Three new Pydantic models appended under a `# Batch read models` section:
- `BatchLabelRecord` — `id`, `name`, `attached_at` (ISO-8601 string)
- `BatchLabelsRequest` — `object_ids: list[str]`, `object_type: str`
- `BatchLabelsResponse` — `labels: dict[str, list[BatchLabelRecord]]`

### `app/service.py`
New method `LabelService.get_labels_for_objects(conn, object_ids, object_type)`:
- Initialises result dict from the input `object_ids` list (zero-fill guarantee)
- Executes a single `WHERE ol.object_id = ANY(%s) AND ol.object_type = %s` query
- Appends `BatchLabelRecord` objects to the appropriate key
- Returns the zero-filled dict

### `app/routers/objects.py`
New route `POST /api/objects/labels/batch` registered **before** the per-object routes to avoid FastAPI matching `labels` as an `object_id` path parameter.

Validation order:
1. Empty `object_ids` → return `BatchLabelsResponse(labels={})` immediately
2. `len(object_ids) > 200` → 422 `BATCH_TOO_LARGE`
3. `object_type` empty after strip → 422 `OBJECT_TYPE_REQUIRED`
4. Call `LabelService.get_labels_for_objects` and return result

### `tests/test_objects.py`
Seven batch-endpoint test stubs added; bodies deferred to Test_Writer.

## Design gaps encountered
None. The design was complete and unambiguous.

## Decisions made during implementation
- `CORS` policy for `POST` is already covered by `allow_methods=["GET", "POST", "DELETE"]` in `app/main.py` — no change needed.
- Route ordering verified: `/objects/labels/batch` is now the first `@router.post` registered in `objects.py`, before `/objects/{object_id}/labels`.
