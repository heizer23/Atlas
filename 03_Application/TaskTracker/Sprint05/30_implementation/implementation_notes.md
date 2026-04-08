# Sprint05 Implementation Notes

## Files Changed

- `03_Application/TaskTracker/schema.sql` — updated check constraint
- `03_Application/TaskTracker/migrations/003_add_pending_status.sql` — new migration
- `03_Application/TaskTracker/backend/routers/tasks.py` — VALID_STATUS, view param, PUT set-labels
- `03_Application/TaskTracker/src/ShellEntry.tsx` — all frontend changes

---

## 1. Complete button (icon, reversible)

`TaskCard`: replaced text button with a `✓` icon button. Removed `disabled`. Both states same size (`minWidth: 36px`, `padding: 3px 10px`). Done state styled with primary color and border; open state in muted on-surface-variant. `handleCompleteToggle` passes `'open'` or `'done'` based on current state.

`TasksPage.handleMarkComplete` now accepts `newStatus: 'done' | 'open'` and PATCHes accordingly. After toggle, calls `fetchTasks(view)` rather than an optimistic update — this ensures the task correctly leaves/enters the Active view (e.g. a just-completed task appears with strikethrough in Active until the next re-fetch cycle, or simply disappears from Done view when reverted).

## 2. Labels removed from list view

Removed the label chips block from `TaskCard`. Labels are still embedded in `TaskRow.labels` (backend unchanged) and are still used by `TaskGroupedList` for grouping logic.

## 3. Priority as symbol

Added `PRIORITY_SYMBOL` map: `high → ↑`, `medium → –`, `low → ↓`. Priority span uses `title={priorityFullName}` for hover tooltip. Width reduced from `52px` to `24px` since a single character is narrower than text.

## 4. Three-dot menu: Add label

- `ThreeDotsMenu`: added `onAddLabel` prop; "Add label" item added at top of menu.
- `LabelPopover`: new component rendered inside `TaskCard` (in a relative-positioned wrapper alongside ThreeDotsMenu). Typeahead input with 200ms debounce, uses `GET /tasks/labels/search?q=...`. Selecting or pressing Enter calls `POST /tasks/{task_id}/labels`. Closes on Escape or click-outside via document-level listeners. On successful attachment, calls `onAttached()` which triggers `fetchTasks(view)` in TasksPage.
- `TaskCard`: manages `labelPopoverOpen` state locally. ThreeDotsMenu.onAddLabel opens the popover; LabelPopover.onAttached closes it and calls the parent's `onAddLabel` (which re-fetches).
- `TaskGroupedList` and `TasksPage`: wired `onAddLabel` prop through.

## 5. Pending status

- `schema.sql`: check constraint updated to `('open', 'in_progress', 'pending', 'done')`.
- `migrations/003_add_pending_status.sql`: drops existing status check constraint (trying both standard and `check1` suffix), re-adds with pending included.
- `tasks.py`: `VALID_STATUS` set updated.
- `TaskDetailEdit`: `<option value="pending">Pending</option>` added between In Progress and Done.

## 6. Three views

`ViewTab` type: `'active' | 'pending' | 'done'`. Default: `'active'`.

`viewFetchUrl()` helper maps view to fetch URL:
- `active` → `GET /tasks?view=active`
- `pending` → `GET /tasks?status=pending`
- `done` → `GET /tasks?status=done`

`fetchTasks` now accepts `currentView` parameter; called on mount and on view change via `useEffect([fetchTasks, view])`.

Tab bar: three buttons with active/inactive styles. Rendered above the task list, border-bottom flush with the page content area.

Per-view toggle: rendered right-aligned in the same bar. Two-button toggle showing the two most related views. Active state non-clickable (same view). Clicking the other option calls `setView(...)`.

Backend `GET /tasks?view=active` query:
```sql
WHERE status IN ('open', 'in_progress')
   OR (status = 'done' AND updated_at::date >= CURRENT_DATE)
```
Count query uses identical WHERE clause.

## 7. PUT /tasks/{task_id}/labels

New endpoint after `DELETE /{task_id}/labels/{label_id}`. Uses a single `httpx.Client` context for all LabelEngine calls. Steps: fetch current labels, delete each, attach each new label by name, return refreshed label list. Empty body `{"labels": []}` clears all labels.

Variable naming: loop variable uses `raw_name` / `name` to avoid shadowing the outer scope.

---

## Known caveats

- Migration `003` uses `DROP CONSTRAINT IF EXISTS` with both `tasks_status_check` and `tasks_status_check1` to handle Postgres auto-naming. If the constraint has a different auto-assigned name, a manual `\d tasktracker.tasks` check will be needed before applying.
- After marking a task complete/open from the list, the page re-fetches. This means the task may disappear from view (e.g. a done task disappears from Active view on next fetch). This is correct behavior per the draft's Active view definition.
