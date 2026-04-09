# TaskTracker Sprint06 — Label Contract Fix

## Context

An architecture audit (LabelEngine_auditrun_04_09_2026) identified three high-severity findings
in TaskTracker's label integration. This sprint resolves all of them.

**F-001 — boundary_drift:** `fetch_labels_for_tasks` (tasks.py:72–95) queries LabelEngine's
internal `labels.*` schema directly via SQL using TaskTracker's own DB pool. This bypasses the
LabelEngine HTTP API for reads while writes correctly use it. Root cause: LabelEngine had no
batch read endpoint. That is now fixed (LabelEngine Sprint02 added
`POST /api/objects/labels/batch`). TaskTracker must now use it.

**F-002 — contract_violation:** `GET /tasks/labels/search` and `GET /tasks/{task_id}/labels`
return LabelEngine's bespoke shapes (`{ labels: [...] }`) verbatim to the UI. R-CON-BP-04
requires all read endpoints to return `Dataset`. The LabelEngine architecture.json explicitly
anticipated Dataset-shaped responses from these proxies. The implementation did not follow through.

**F-003 — exception_missing_record:** Resolved automatically once F-001 and F-002 are fixed.

Mutation endpoints (POST, PUT, DELETE on labels) are out of scope — they are not "read" endpoints
and Dataset does not fit mutation acknowledgments. A separate rule clarification to R-CON-BP-04
will address those; no code change needed here.

## Changes required

### 1. Replace `fetch_labels_for_tasks` with LabelEngine batch API call

Remove the SQL function `fetch_labels_for_tasks` from `backend/routers/tasks.py`.

Replace it with a call to `POST /api/objects/labels/batch` via `_label_client()`:

```python
def fetch_labels_for_tasks(task_ids: list[str]) -> dict[str, list[dict]]:
    if not task_ids:
        return {}
    with _label_client() as client:
        resp = client.post(
            "/api/objects/labels/batch",
            json={"object_ids": task_ids, "object_type": "task"},
        )
    if resp.status_code != 200:
        return {}
    return resp.json().get("labels", {})
```

- Remove the `conn` parameter — no DB access needed.
- Update the call site in `list_tasks` (tasks.py:229–233) to drop the `conn` argument.
- The return shape from the batch endpoint is `{object_id: [{id, name, attached_at}]}`;
  the existing row-building code (`r["labels"] = labels_by_task.get(r["id"], [])`) can
  remain as-is since `id` and `name` are present in each record.

### 2. Transform `search_labels` to return Dataset

`GET /tasks/labels/search` currently proxies `{ labels: [{id, name}] }`.

Transform to:
```python
Dataset(
    meta=DatasetMeta(object_type="label", label="Labels", total=len(items), page=1, page_size=len(items), row_actions=[]),
    schema=[
        ColumnSchema(key="id", label="ID", type="string"),
        ColumnSchema(key="name", label="Name", type="string"),
    ],
    rows=[{"id": item["id"], "name": item["name"]} for item in items],
)
```

### 3. Transform `get_task_labels` to return Dataset

`GET /tasks/{task_id}/labels` currently proxies `{ labels: [{object_id, label_id, label_name, attached_at}] }`.

Transform to:
```python
Dataset(
    meta=DatasetMeta(object_type="task_label", label="Task Labels", total=len(items), page=1, page_size=len(items), row_actions=["delete"]),
    schema=[
        ColumnSchema(key="id", label="ID", type="string"),
        ColumnSchema(key="name", label="Name", type="string"),
        ColumnSchema(key="attached_at", label="Attached", type="date"),
    ],
    rows=[{"id": lbl["label_id"], "name": lbl["label_name"], "attached_at": lbl["attached_at"]} for lbl in items],
)
```

Note: use `label_id` as the row `id` field (it is the stable identity for the attachment).

### 4. Update ShellEntry.tsx to consume Dataset shapes

For `search_labels` consumers (autocomplete suggestions):
- Currently: `(res as { labels: LabelRecord[] }).labels`
- Change to: `res.rows.map(r => ({ id: r.id as string, name: r.name as string }))`

For `get_task_labels` consumers (attached label display):
- Currently: `(res as { labels: AttachedLabel[] }).labels`
- Change to: `res.rows.map(r => ({ label_id: r.id as string, label_name: r.name as string, attached_at: r.attached_at as string }))`

Update the three call sites in ShellEntry.tsx (lines ~435–436, ~732–733, ~893–895).

## Out of scope

- Mutation proxy endpoints (POST attach, DELETE detach, PUT set): no change — rule clarification
  will handle these at the governance level.
- `set_task_labels` (PUT): no change.
- The embedded `labels` field in `list_tasks` Dataset rows / `TASK_SCHEMA` declaration (F-004):
  separate concern, separate sprint.
- Any LabelEngine changes.

## Verification

After implementation:
- `GET /tasks/labels/search?q=` returns `{ meta, schema, rows }` with `id` and `name` columns.
- `GET /tasks/{task_id}/labels` returns `{ meta, schema, rows }` with `id`, `name`, `attached_at` columns.
- Label autocomplete and tag display in the UI still function correctly.
- `list_tasks` no longer triggers a SQL query against `labels.*` — labels arrive via the batch HTTP call.
- No `ARCHITECTURE_EXCEPTIONS.md` is needed (no remaining unregistered deviation).
