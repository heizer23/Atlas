# TaskTracker Sprint05 — UI Polish + Views + Pending Status

## Summary

Six changes to task list UX, a new status value, three filtered views, and a set-labels API for Chronos.

---

## 1. Complete button — icon, same size, reversible

**Current:** "Complete" / "Done" text button on each task row. Disabled when done.

**Change:**
- Replace text with a checkmark icon: `✓` (unchecked style when open, filled/checked style when done).
- Both states render the same button size — no layout shift.
- Make it reversible: clicking the icon on a `done` task sets it back to `open`.
- Visual distinction between states (e.g. outline vs filled, or opacity/color change) — not disabled.

Backend: no change — `PATCH /tasks/{id}` with `{ status: "open" }` already works.

Frontend: update `TaskCard`. Remove `disabled` on done. Toggle between `open` and `done` on click.

---

## 2. Labels not shown in list view

**Current:** Label chips are rendered on each `TaskCard` row.

**Change:** Remove label chips from the task card row in the grouped list. Labels are still used for grouping (first label = group key). The group header already makes the primary label visible.

Frontend only: remove the label chip block from `TaskCard`. No API change.

---

## 3. Priority as symbol

**Current:** Priority shown as coloured text chip: "High" / "Medium" / "Low".

**Change:** Replace text with a compact symbol. Suggested mapping:

| Priority | Symbol |
|----------|--------|
| high     | `↑`   |
| medium   | `–`   |
| low      | `↓`   |

Retain the colour coding (red / amber / muted). Symbol only — no text label. Same fixed column width. Tooltip on hover: full priority name.

Frontend only: update `TaskCard` priority rendering.

---

## 4. Three-dot menu: Add label

**Current:** Three-dot menu has: Link, Delete.

**Change:** Add "Add label" item at the top of the menu.

Clicking "Add label" opens an inline popover (attached to the row) with:
- Typeahead input — same search logic as the detail screen (`GET /tasks/labels/search?q=...`)
- Selecting a suggestion attaches it (`POST /tasks/{task_id}/labels`)
- Typing and pressing Enter creates + attaches a new label
- Popover closes on Escape or clicking outside

This allows label attachment from the list without opening the detail screen.

Frontend: extend `ThreeDotsMenu` to accept `onAddLabel` prop. Add inline `LabelPopover` component rendered relative to the menu. Wire through `TaskGroupedList` and `TasksPage`. On attach success, re-fetch tasks so grouping updates.

---

## 5. New status: Pending

**Change:** Add `pending` as a valid task status alongside `open`, `in_progress`, `done`.

Semantics: task is waiting on something external — not actively worked, not done.

**Backend:**
- `schema.sql` migration: alter the check constraint to `status in ('open', 'in_progress', 'pending', 'done')`.
- `tasks.py`: add `'pending'` to `VALID_STATUS`.

**Frontend:**
- `TaskDetailEdit`: add `<option value="pending">Pending</option>` to the status select.

No new DB column. No migration file needed beyond updating the check constraint.

---

## 6. Three views: Active, Pending, Done

Replace the single flat task list with three filtered views.

### View definitions

| View    | Shows                                                                 | Toggle button        |
|---------|-----------------------------------------------------------------------|----------------------|
| Active  | open + in_progress tasks; **plus** done tasks completed today         | [Active \| Done]     |
| Pending | pending tasks                                                         | [Pending \| Active]  |
| Done    | all done tasks, ordered by `updated_at desc`                          | [Active \| Done]     |

**Active view detail:**
- Done tasks completed today (`updated_at::date = current_date`) remain visible with strikethrough — same as current behaviour.
- Done tasks completed before today are hidden. Backend filter: `status IN ('open', 'in_progress') OR (status = 'done' AND updated_at::date >= CURRENT_DATE)`.

### Navigation

A tab bar in the page header:

```
[ Active ]  [ Pending ]  [ Done ]
```

- Default: Active.
- Tab state is local component state (not URL param).
- Each tab switch re-fetches with the appropriate filter.

In addition, each view renders its own **2-state toggle button** (separate from the tab bar) that navigates between the two related views:

- On Active tab: toggle shows **[Active | Done]** — clicking Done switches to the Done tab.
- On Pending tab: toggle shows **[Pending | Active]** — clicking Active switches to the Active tab.
- On Done tab: toggle shows **[Active | Done]** — clicking Active switches to the Active tab.

The toggle button provides a quick flip between the two most related views without scanning the full tab bar. Both the tab bar and the toggle button keep the current tab in sync.

### Backend

`GET /tasks?status=...` already supports single-status filtering. Two changes needed:

1. **Multi-status filter** for Active view:
   ```
   GET /tasks?status=open,in_progress,done&done_since=today
   ```
   Simpler alternative: add a `view=active` query param that applies the Active logic server-side. The implementer may choose the approach.

2. **Date filter for Active view done tasks:** backend must accept a constraint that limits done tasks to `updated_at::date >= CURRENT_DATE`. One clean option: `GET /tasks?view=active` returns the full Active definition in one query.

---

## 7. API: Set labels (for Chronos)

**Current:** Labels can only be attached or detached one at a time. Chronos (and other callers) need a way to set the full label set atomically.

**New endpoint:**

```
PUT /tasks/{task_id}/labels
Body: { "labels": ["Outside", "Errand"] }
```

Semantics: replace all current labels on the task with the provided list. Empty list clears all labels.

Implementation:
1. Detach all existing labels for the task (via LabelEngine `DELETE /api/objects/{id}/labels/{label_id}` for each).
2. Attach each provided label by name (via LabelEngine `POST /api/objects/{id}/labels`).
3. Return the updated label list in the same shape as `GET /tasks/{task_id}/labels`.

This is a synchronous operation. The LabelEngine calls are sequential.

---

## Acceptance criteria

- [ ] Complete/undo icon button: clicking a done task marks it open again; both states same size
- [ ] Label chips absent from task card rows in list view
- [ ] Priority shown as symbol (↑ / – / ↓) with colour and hover tooltip
- [ ] Three-dot menu includes "Add label"; popover attaches labels inline from the list
- [ ] `pending` is a valid task status in DB, backend, and frontend status select
- [ ] Three view tabs: Active / Pending / Done with tab bar navigation
- [ ] Each view has its own 2-state toggle button (Active↔Done, Pending↔Active, Active↔Done)
- [ ] Active view includes today's done tasks (strikethrough); hides done tasks from before today
- [ ] `PUT /tasks/{task_id}/labels` atomically replaces labels; empty list clears all
- [ ] All existing functionality unchanged (detail edit, linking, create form)

---

## Files expected to change

- `03_Application/TaskTracker/src/ShellEntry.tsx` — views, TaskCard, ThreeDotsMenu, LabelPopover
- `03_Application/TaskTracker/backend/routers/tasks.py` — VALID_STATUS, set-labels endpoint, optional multi-status filter
- `03_Application/TaskTracker/schema.sql` — check constraint update
- DB migration required for `pending` status constraint change
