# Sprint04 Implementation Notes

## Changes implemented

### 1. GET /tasks includes labels (backend)

`backend/routers/tasks.py`:

- Added `fetch_labels_for_tasks(conn, task_ids)` — single batch SQL query joining `labels.object_labels` and `labels.labels` for all task IDs in the page. Returns `{task_id: [{id, name}, ...]}`.
- `list_tasks` now calls this after fetching tasks and embeds `labels: [{id, name}]` into each row dict before returning the Dataset.
- Labels are ordered by `attached_at ASC` (first attached = primary label, consistent with LabelEngine primary-label rule).
- The `labels` field is not added to `TASK_SCHEMA` (it is not a display column; it passes through as an undeclared row field per the Dataset contract, which silently ignores undeclared fields).
- Queries the `labels` schema directly (same Postgres instance, same connection). No extra HTTP calls to LabelEngine per task.

### 2. Task overview grouped by primary label (frontend)

`src/ShellEntry.tsx`:

- Added `TaskGroupedList` component. Groups tasks by `task.labels[0]?.name` (primary label = first attached). Tasks with no labels appear under "Unlabeled" at the end. Named groups are sorted alphabetically.
- `TasksPage` renders `TaskGroupedList` instead of a flat list.
- Group headers rendered as small uppercase label text above each group's task list.

### 3. Mark Complete as direct row button (frontend)

- `ThreeDotsMenu`: removed `onMarkComplete` prop and the "Mark complete" menu item. Remaining items: Link, Delete.
- `TaskCard`: added a visible "Complete" / "Done" button directly on the row. Button is disabled when task is already done. Click calls `onMarkComplete` without opening the menu.
- `TaskCard` no longer fetches labels separately — uses `task.labels` from the row data returned by the API.

### 4. New task default priority = Medium (frontend)

- `TASK_FIELDS`: added `initialValue: 'medium'` to the priority field. This uses the existing `FormField.initialValue` contract (R-CON-BP-04 v0.3).

## Files changed

- `/home/linse/Prod/Atlas/03_Application/TaskTracker/backend/routers/tasks.py`
- `/home/linse/Prod/Atlas/03_Application/TaskTracker/src/ShellEntry.tsx`

## Notes

- `TaskDetailEdit` still fetches labels via API for its label management UI — this is intentional, as the detail screen needs the full `AttachedLabel` shape (with `label_id`, `attached_at`) for detach operations. The list view only needs `{id, name}` embedded in the row.
- The label-per-row detach buttons have been removed from `TaskCard`. Label management is available in the detail/edit screen.
- No schema migrations required. No new API endpoints. No new platform components.
