# Implementation Notes — TaskTracker Sprint06_Label_Contract_Fix

**Date:** 2026-04-09
**Implementer:** sprint_implement

## Changes Made

### backend/routers/tasks.py

**fetch_labels_for_tasks (lines 72–82)**
- Removed `conn: Any` parameter and entire SQL body
- Replaced with HTTP call to `POST /api/objects/labels/batch` via `_label_client()`
- Returns `{}` on empty input or non-200 response
- Return type narrowed from `dict[str, list[dict[str, str]]]` to `dict[str, list[dict]]` (batch response includes `attached_at`)

**list_tasks call site (line ~231)**
- Removed `conn` argument: `fetch_labels_for_tasks(conn, task_ids)` → `fetch_labels_for_tasks(task_ids)`
- The `labels_by_task.get(r["id"], [])` row-building code is unchanged — batch response keys are task IDs as expected

**search_labels (GET /tasks/labels/search)**
- Replaced pass-through `JSONResponse` with Dataset construction
- Non-200 from LabelEngine propagated directly
- Schema: `[id: string, name: string]`; `meta.object_type = "label"`; `row_actions = []`

**get_task_labels (GET /tasks/{task_id}/labels)**
- Replaced pass-through `JSONResponse` with Dataset construction
- Non-200 from LabelEngine propagated directly
- Schema: `[id: string, name: string, attached_at: date]`; `meta.object_type = "task_label"`; `row_actions = ["delete"]`
- Row mapping: `label_id` → `id`, `label_name` → `name`, `attached_at` → `attached_at`

### src/ShellEntry.tsx

Four call sites updated from `{ labels: T[] }` shape to `{ rows: {...}[] }` Dataset shape:

1. **LabelPanel.handleQueryChange (~line 435)** — search autocomplete → `res.rows.map(r => ({id, name}))`
2. **TaskEditPanel.handleLabelQueryChange (~line 732)** — search autocomplete → `res.rows.map(r => ({id, name}))`
3. **TaskEditPanel useEffect get_task_labels (~line 893)** — attached label load → `res.rows.map(r => ({label_id: r.id, label_name: r.name, attached_at: r.attached_at}))`
4. **TaskCreatePanel.handleLabelQueryChange (~line 1102)** — search autocomplete → `res.rows.map(r => ({id, name}))`

## No-Change Items (confirmed out of scope)

- `attach_task_label` (POST), `detach_task_label` (DELETE), `set_task_labels` (PUT): unchanged
- `TASK_SCHEMA` and `list_tasks` Dataset structure: unchanged
- No LabelEngine changes

## Design Gap Notes

- The open question in architecture.json (propagate vs wrap non-200 errors) was resolved by propagating the upstream status code and body directly, matching the existing pattern in the mutation proxy endpoints.
- `set_task_labels` at line ~405 reads `resp.json().get("labels", [])` using the old `label_id`/`label_name` shape from LabelEngine's per-object GET — this is out of scope and unchanged.
