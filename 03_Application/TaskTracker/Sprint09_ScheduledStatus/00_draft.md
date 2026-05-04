# Sprint 09 — Scheduled Status

## Goal

Add a `scheduled` task status and a `Scheduled` tab to TaskTracker.
A scheduled task has a planned date+time. It is excluded from the Active tab until
the scheduled time arrives, at which point the backend promotes it to `active`
automatically. No Google Calendar integration in this sprint — scheduling is manual.

---

## Status vocabulary (full set after this sprint)

| Status | Meaning |
|--------|---------|
| `open` | Created, not yet started |
| `in_progress` | Actively being worked on (same as the current `active` view) |
| `scheduled` | Has a future blocker; excluded from Active tab |
| `pending` | Blocked, waiting on something external |
| `done` | Completed |

> **Note:** The existing `status` check constraint uses `open`, `in_progress`, `pending`,
> `done`. This sprint adds `scheduled` to that constraint. No existing rows are affected.

---

## Time authority

Server time governs promotion. `scheduled_at` is stored as `timestamptz`.
Auto-promotion condition: `scheduled_at::date <= CURRENT_DATE` (server-side, UTC).
Promotion happens as a side-effect of the `/tasks?view=active` and
`/tasks?view=pending_board` fetch: the backend runs a single UPDATE before the SELECT,
setting `status = 'in_progress'` for any `scheduled` tasks meeting the condition.
Client time is never used for activation decisions.

---

## Data layer

### Migration: `migrations/009_scheduled_status.sql`

```sql
ALTER TABLE tasktracker.tasks
    DROP CONSTRAINT IF EXISTS tasks_status_check;

ALTER TABLE tasktracker.tasks
    ADD CONSTRAINT tasks_status_check
        CHECK (status IN ('open', 'in_progress', 'scheduled', 'pending', 'done'));

ALTER TABLE tasktracker.tasks
    ADD COLUMN IF NOT EXISTS scheduled_at timestamptz;

CREATE INDEX IF NOT EXISTS ix_tasks_scheduled_at
    ON tasktracker.tasks(scheduled_at)
    WHERE status = 'scheduled';
```

---

## Backend

File: `backend/routers/tasks.py`

### Schema changes

- Add `scheduled_at` to `TASK_SCHEMA` as a `ColumnSchema` entry:
  `key='scheduled_at', label='Scheduled', type='string', sortable=True, filterable=False`
- Add `scheduled` to the `status` enum validation in `TaskCreate` and `TaskUpdate`.
- Add `scheduled_at: datetime | None = None` (optional) to both `TaskCreate` and `TaskUpdate`.

### Auto-promotion side-effect

Before executing the SELECT for `view=active` and `view=pending_board`, run:

```sql
UPDATE tasktracker.tasks
   SET status = 'in_progress', updated_at = now()
 WHERE status = 'scheduled'
   AND scheduled_at IS NOT NULL
   AND scheduled_at::date <= CURRENT_DATE;
```

This is a plain UPDATE inside the same DB transaction as the SELECT.
No background job, no scheduler — promotion is lazy and triggered by page load.

### New view: `view=scheduled`

Returns tasks with `status = 'scheduled'`, ordered by `scheduled_at ASC NULLS LAST`.
No label filtering applied (scheduled tasks are shown regardless of active label filter).

### Active view change

`view=active` already filters by status. After the auto-promotion UPDATE, the SELECT
must explicitly exclude `scheduled`:

```sql
WHERE status NOT IN ('done', 'pending', 'scheduled')
```

(Currently the active query uses `view=active` semantics; make the exclusion explicit.)

### Validation rule

If `status = 'scheduled'` is submitted without `scheduled_at`, return:
`api_error('VALIDATION_ERROR', 'scheduled_at is required when status is scheduled')`

If `scheduled_at` is provided with a status other than `scheduled`, accept it
(store for later use) — do not reject.

---

## Frontend

File: `src/ShellEntry.tsx`

### Tab bar

Add a fourth tab: `Scheduled`. Tab order: Active | Scheduled | Pending | Done.
Route: `/tasks/scheduled`.
`ViewTab` type becomes `'active' | 'scheduled' | 'pending' | 'done'`.

### `viewFetchUrl` change

```ts
if (view === 'scheduled') return '/tasks?view=scheduled';
```

### Route detection

```ts
const view: ViewTab =
  location.pathname === '/tasks/scheduled' ? 'scheduled' :
  location.pathname === '/tasks/pending'   ? 'pending'   :
  location.pathname === '/tasks/done'      ? 'done'      : 'active';
```

### Scheduled tab rendering

- Each row shows: task title, scheduled date (formatted `"Mon 5 May 09:00"`), priority chip.
- Sorted by `scheduled_at` ascending (backend already returns in this order).
- Tapping a row opens the task detail (same `TaskDetailEdit` as other tabs).
- No section grouping needed in this sprint.

### Task detail — `scheduled_at` field

In `TaskDetailEdit`, add a `datetime-local` input for `scheduled_at`.
Only shown when `status === 'scheduled'` or when the user selects `scheduled` in the
status dropdown.
When status is changed away from `scheduled`, clear `scheduled_at` in the form state
(send `null` in the PATCH body).

Status dropdown must include `scheduled` option.

### Create form

Add `scheduled` as an option in the status dropdown of `TaskCreateForm`.
When selected, show a `datetime-local` field for `scheduled_at` (required).
On submit with `status=scheduled`, include `scheduled_at` in the POST body.
After creation, navigate to the Scheduled tab.

### `TaskRow` type

Add `scheduled_at: string | null` to the `TaskRow` interface.

---

## Shell config

File: `src/shellConfig.ts`

Add `/tasks/scheduled` to the navigation if it is declared there (check existing pattern).

---

## Scope exclusions

- No Google Calendar integration.
- No LinkingEngine usage in this sprint.
- No push notifications on promotion.
- No recurring scheduled tasks.
- Rescheduling in this sprint = edit `scheduled_at` manually in task detail and save.

---

## Open questions (resolved)

| Question | Resolution |
|----------|------------|
| Time authority | Server UTC; `scheduled_at::date <= CURRENT_DATE` |
| Promotion trigger | Lazy on active/pending page load — no background job |
| `scheduled_at` with non-scheduled status | Accepted and stored; not rejected |
| Label filter on Scheduled tab | Not applied — show all scheduled tasks |
