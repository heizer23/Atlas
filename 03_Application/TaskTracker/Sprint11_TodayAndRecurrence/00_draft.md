# Sprint 11 — Today/Upcoming View and Recurring Tasks

## Goal
Add (1) an agenda-style **Today / Upcoming** view and (2) **recurring tasks**
to TaskTracker. Keep both small; reuse existing columns, views and label wiring.

Boundary with HabitTracker: tasks with a deadline recur here; streak-style habits stay in HabitTracker. No cross-app integration.

---

## Part A — Today / Upcoming view

### Behavior
New tab **Today** (first tab, default landing). Sections, in order:
1. **Overdue** — not done, effective date < today
2. **Today** — effective date = today
3. **Next 7 days** — grouped by day (tomorrow … today+7), each day header shows total `effort_hours`

**Effective date** = `scheduled_at` if status=`scheduled`, else `due_date`.
Done and `training_unit` tasks are excluded. Tasks with no effective date do not appear (they stay in the existing Pending tab).
Today section header shows total planned effort (sum of `effort_hours`, null = 0).
`in_progress` tasks with no date are NOT shown (out of scope).
Existing auto-promotion of due `scheduled` tasks runs before the query (as in `active`/`pending_board`).

### Backend
- New `view=agenda` on `GET /tasks` (or dedicated `GET /tasks/agenda` if cleaner for the UI data contract R-CON-BP-04 — designer decides). Returns rows with labels embedded, plus an `agenda_bucket` field (`overdue` | `today` | `upcoming`) and `agenda_date`.
- No pagination issues: window is bounded (overdue + 8 days).
- "Today" uses server date (same convention as existing `current_date` usage).

### Frontend
- Tab + sectioned list; row reuses existing task row/actions (complete, edit, status change).
- Empty state when nothing is due.
- Completing a task updates the list in place.

---

## Part B — Recurring tasks

### Model (new columns on `tasktracker.tasks`, idempotent migration + schema.sql)
- `recurrence_freq`      text null, check in (`daily`,`weekly`,`monthly`)
- `recurrence_interval`  integer not null default 1, check >= 1
- `recurrence_mode`      text not null default `fixed`, check in (`fixed`,`after_completion`)
- `recurrence_next_id`   uuid null (the spawned successor; idempotency guard; no FK cascade issues — on delete set null)

Recurring iff `recurrence_freq is not null`. A recurring task requires `due_date` (or `scheduled_at`) unless mode=`after_completion`.
No weekday sets, no end dates, no "nth weekday" in this sprint (note as future).
`task_type` must be `normal` for recurring tasks.

### Behavior
When a recurring task transitions to `done` and `recurrence_next_id is null`:
- Create successor in the same transaction: same title, description, priority, effort_hours, labels, recurrence_* fields; status `open`; `completed_at` null; `actual_duration_minutes` null; `parent_task_id` same as source.
- Next date:
  - `fixed`: anchor = source's due_date (or scheduled_at); add interval; **if result <= today, keep adding until > today** (no pile-up of past occurrences after a long gap).
  - `after_completion`: today + interval.
- If source was `scheduled` (has `scheduled_at`), successor is `scheduled` with shifted `scheduled_at` (and due_date shifted by same delta if present); calendar blocker created via existing sync helper. Otherwise successor is `open` with shifted `due_date`.
- Store successor id in source `recurrence_next_id`.
- Un-doing and re-doing the source does NOT spawn a second successor (guarded by `recurrence_next_id`).
- Labels are copied via the existing label service (best-effort; failure logged, task creation still succeeds).
- Deleting/marking done a successor chain is independent — each occurrence is its own row; history is preserved as done tasks.

### API
- `POST /tasks` and `PATCH /tasks/{id}` accept `recurrence_freq`, `recurrence_interval`, `recurrence_mode`; `recurrence_freq: null` clears recurrence. Validation errors via existing `api_error`.
- Responses and column schema include the recurrence fields; add human summary field `recurrence_label` (e.g. "Every 2 weeks", "Daily, after completion").

### Frontend
- Create/edit form: "Repeat" control — none / daily / weekly / monthly, interval number, "from completion date" toggle.
- Recurring tasks show a repeat icon + `recurrence_label` in row/detail.
- When completing a recurring task, brief toast: "Next: <date>".

---

## Out of scope
Weekday sets, end dates/counts, skipping one occurrence, editing "this and future", reminders/notifications, drag-reorder, quick-add parsing, HabitTracker integration, Today view for undated `in_progress` tasks.

## Acceptance
- Agenda view returns correct buckets across: overdue, today, +7 boundary, scheduled vs due-date precedence, done excluded, training_unit excluded.
- Completing each recurrence combination (daily/weekly/monthly × fixed/after_completion, incl. month-end clamp e.g. Jan 31 + 1 month → Feb 28/29, and long-overdue catch-up) yields exactly one successor with the right date.
- Re-done after undo creates no duplicate.
- Scheduled recurring task: successor scheduled with calendar blocker.
- Existing views/tests unaffected.

## Notes
- Migration must be idempotent (`add column if not exists`), per existing schema.sql pattern; add migration file under `migrations/`.
- Frontend deploy: Stop hook handles vite build + docker cp. Backend rebuild needs `--env-file 01_System/secrets.env` + `config.env`.
