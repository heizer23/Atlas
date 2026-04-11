# Sprint07 — Label Filter

## Component
TaskTracker (`03_Application/TaskTracker`)

## Goal
Add a filter-by-label UI to the TaskTracker task list view.

## Feature Description

### Label filter dropdown
- Displayed above (or alongside) the task list, persistent across all three tabs: **Active**, **Pending**, **Done**
- Populated with every label that has at least one association to any task (i.e. only labels in use appear)
- Supports:
  - **Select All** — activates all labels (default state on load)
  - **Deselect All** — deactivates all labels (shows no tasks)
  - **Individual toggle** — each label can be selected or deselected independently

### Filtering behavior
- When all labels are selected (default), all tasks are shown (no change from current behavior)
- When a subset of labels is selected, only tasks that carry at least one of the selected labels are shown
- The filter state is shared across tabs — switching from Active to Pending to Done preserves the current selection
- Filter state is in-memory only (not persisted to the backend or localStorage)

### Backend
- A new read endpoint is needed to fetch all labels currently associated with at least one task: `GET /labels/active` (or similar)
- The existing task list endpoints should accept an optional `label_ids` query parameter (multi-value) to return only tasks matching those labels
- If `label_ids` is omitted, all tasks are returned (backwards-compatible)

## Out of Scope
- Persisting filter state across page reloads
- Filtering by label in any view other than the main task list tabs
- Creating, editing, or deleting labels (handled by existing label management)
