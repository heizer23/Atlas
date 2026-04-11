# Sprint08 — TaskTracker Label Filter Wiring

## Component
TaskTracker (`03_Application/TaskTracker`)

## Layer
Application (`03_Application`)

## Goal
Replace the Sprint07 label filter workaround with correct platform-backed behavior: labels loaded from LabelEngine, filter state persisted in PreferenceStore, and filter stable across tab switches.

## Background
Sprint07 implemented label filtering by deriving the available label list from whichever task rows happened to be loaded for the current tab. This caused two bugs:
1. The label list changed per tab (only labels on tasks in that tab were shown)
2. The filter reset when switching tabs because `activeLabels` was re-derived on each fetch

The correct architecture: LabelEngine owns label-object associations; PreferenceStore owns user filter preferences.

## What changes

### Backend
- **Remove** `GET /tasks/labels/active` from TaskTracker — this endpoint was a workaround and is now replaced by LabelEngine's `GET /api/labels/used?object_type=task`.
- **Remove** the `label_ids` query parameter from `GET /tasks` — it was declared as a forward-compatibility hook but was never implemented server-side. Client-side filtering via the frontend is sufficient for now and is clearly documented.

### Frontend (`ShellEntry.tsx`)

**Label loading (fix tab reset — root cause)**
- On `TasksPage` mount (once), call LabelEngine `GET /api/labels/used?object_type=task` to get the full label list.
- Store this in `availableLabels` state. This list does not change on tab switch.
- Remove the label-derivation logic inside `fetchTasks` entirely.

**Filter state persistence (new)**
- On mount, after loading available labels, call PreferenceStore `GET /preferences/tasktracker.task-list/label_filter`.
  - If found: initialise `selectedLabelIds` from the stored array of label IDs (intersected with currently available labels to handle stale IDs).
  - If 404: default to all labels selected.
- Whenever `selectedLabelIds` changes, call PreferenceStore `PUT /preferences/tasktracker.task-list/label_filter` with the current set as a JSON array.

**Tab switch behavior**
- `selectedLabelIds` is top-level state in `TasksPage`, unchanged by tab switching.
- `fetchTasks` no longer touches label state.
- The filter bar renders from `availableLabels` (stable) and `selectedLabelIds` (stable).

## Platform dependencies
- LabelEngine `GET /api/labels/used?object_type=task` (added in Sprint02_ReverseLookup — must be deployed first)
- PreferenceStore `GET /preferences/{scope}/{key}` and `PUT /preferences/{scope}/{key}` (added in Sprint01_Init — already deployed)

## Out of Scope
- Server-side filtering on `GET /tasks`
- Any new backend endpoints
- Any label management UI changes
