# Test Spec — TaskTracker — Sprint11_TodayAndRecurrence

## Scope
Agenda endpoint, recurrence fields on create/update, successor spawning on completion, and the Today tab / Repeat control / next-date toast; out of scope are weekday sets, end dates, notifications, HabitTracker, and behaviour of unchanged label/preference proxies.

Notation: "today" means the database's current date; "today+N" / "today-N" are offsets from it. Agenda scenarios assume the existing fixture tasks (fix-scheduled-future at today+7, fix-scheduled-further at today+14, fix-scheduled-past at today-1) are present unless a scenario says otherwise.

## Scenarios

### Agenda — overdue task bucketed
- **Given:** an open task with due_date today-2
- **When:** GET the agenda
- **Then:** the task is returned with agenda_bucket "overdue" and agenda_date equal to today-2

### Agenda — due today bucketed
- **Given:** an open task with due_date today
- **When:** GET the agenda
- **Then:** the task is returned with agenda_bucket "today" and agenda_date equal to today

### Agenda — upcoming window boundary
- **Given:** open tasks with due_date today+1, today+7 and today+8
- **When:** GET the agenda
- **Then:** the today+1 and today+7 tasks are returned with agenda_bucket "upcoming"; the today+8 task is not returned

### Agenda — scheduled status uses scheduled_at
- **Given:** a task with status scheduled, scheduled_at today+3 and due_date today+6
- **When:** GET the agenda
- **Then:** the task is returned once with agenda_date today+3

### Agenda — non-scheduled status uses due_date
- **Given:** an in_progress task with due_date today+2 and a retained scheduled_at of today-5
- **When:** GET the agenda
- **Then:** the task is returned with agenda_date today+2 (not today-5)

### Agenda — done tasks excluded
- **Given:** a done task with due_date today
- **When:** GET the agenda
- **Then:** the task is not returned

### Agenda — training_unit tasks excluded
- **Given:** a training_unit task with due_date today
- **When:** GET the agenda
- **Then:** the task is not returned

### Agenda — undated tasks excluded
- **Given:** an open task with no due_date and no scheduled_at, and an in_progress task with no dates
- **When:** GET the agenda
- **Then:** neither task is returned

### Agenda — ordering
- **Given:** open tasks: A (due today+2, low), B (due today-3, medium), C (due today+2, high), D (due today, medium)
- **When:** GET the agenda
- **Then:** rows are ordered B, D, C, A (agenda_date ascending, then high before low within the same date)

### Agenda — empty result
- **Given:** no task has a date inside the window (all fixtures removed or out of range)
- **When:** GET the agenda
- **Then:** the response is 200 with a Dataset whose rows are empty and meta total is 0

### Agenda — auto-promotion runs before the query and persists
- **Given:** a scheduled task with scheduled_at today and due_date today+4
- **When:** GET the agenda, then fetch the task via the full task list
- **Then:** the task appears in the agenda with agenda_date today+4 (its status is now in_progress), and the stored status is in_progress

### Agenda — labels embedded and LabelEngine failure tolerated
- **Given:** a dated open task and a LabelEngine that returns labels for it; then the same with LabelEngine unreachable
- **When:** GET the agenda in each case
- **Then:** first case rows carry the labels; second case returns 200 with labels as an empty list on every row

### Agenda — existing views unchanged
- **Given:** the standard fixtures
- **When:** GET tasks with view=active, view=pending_board, view=scheduled and status=done
- **Then:** the same rows and ordering as before this sprint, each row additionally carrying the recurrence fields with recurrence_label null

### Recurrence — create with valid recurrence
- **Given:** a POST body with title, due_date today+1, recurrence_freq weekly, recurrence_interval 2
- **When:** POST the task
- **Then:** 200/201 Dataset row with recurrence_freq weekly, recurrence_interval 2, recurrence_mode fixed, recurrence_next_id null, recurrence_label "Every 2 weeks"

### Recurrence — label formats
- **Given:** tasks created as (daily, 1, fixed), (monthly, 1, fixed), (daily, 1, after_completion), (weekly, 3, after_completion)
- **When:** the rows are read back
- **Then:** recurrence_label is "Daily", "Monthly", "Daily, after completion", "Every 3 weeks, after completion" respectively; a non-recurring task has recurrence_label null

### Recurrence — create validation errors
- **Given:** POST bodies with: freq "yearly"; interval 0; mode "sometimes"; freq weekly with task_type training_unit; freq weekly, mode fixed and no due_date/scheduled_at
- **When:** each is posted
- **Then:** each returns 400 ApiError with code VALIDATION_ERROR and creates no task

### Recurrence — after_completion without dates allowed
- **Given:** a POST body with recurrence_freq daily, recurrence_mode after_completion and no dates
- **When:** POST the task
- **Then:** the task is created successfully

### Recurrence — PATCH null clears recurrence
- **Given:** a recurring task (monthly, interval 3, after_completion)
- **When:** PATCH with recurrence_freq null (interval and mode omitted)
- **Then:** the row has recurrence_freq null, recurrence_interval 1, recurrence_mode fixed, recurrence_label null

### Recurrence — PATCH omit leaves recurrence unchanged
- **Given:** a recurring task (weekly, interval 2)
- **When:** PATCH only the title
- **Then:** recurrence_freq, interval and mode are unchanged

### Recurrence — PATCH explicit null on interval or mode rejected
- **Given:** a recurring task
- **When:** PATCH with recurrence_interval null, and separately with recurrence_mode null
- **Then:** each returns 400 VALIDATION_ERROR and the task is unchanged

### Recurrence — PATCH clearing the only date of a fixed task rejected
- **Given:** a fixed recurring open task whose only date is due_date
- **When:** PATCH due_date null
- **Then:** 400 VALIDATION_ERROR and due_date is unchanged

### Recurrence — due_date explicit null clears on a normal task
- **Given:** a non-recurring open task with due_date today+2
- **When:** PATCH due_date null
- **Then:** the row has due_date null and the task no longer appears in the agenda

### Recurrence — daily fixed spawns next day
- **Given:** an open task, daily every 1, fixed, due_date today+0
- **When:** PATCH status done
- **Then:** exactly one new task exists with due_date today+1, status open; the source row shows recurrence_next_id equal to the new task's id; the PATCH response row carries recurrence_next_date today+1

### Recurrence — weekly fixed with interval
- **Given:** an open task, weekly every 2, fixed, due_date today+1
- **When:** PATCH status done
- **Then:** the successor has due_date today+15

### Recurrence — monthly fixed
- **Given:** an open task, monthly every 1, fixed, due_date today+5
- **When:** PATCH status done
- **Then:** the successor's due_date is one calendar month after today+5, same day-of-month, clamped to the target month's last day

### Recurrence — month-end clamp (date arithmetic)
- **Given:** an anchor of Jan 31 2027, monthly every 1, fixed, with "today" of Jan 30 2027; and an anchor of Jan 31 2028 (leap year) with "today" of Jan 30 2028
- **When:** the next date is computed
- **Then:** the results are Feb 28 2027 and Feb 29 2028

### Recurrence — long-overdue catch-up (date arithmetic)
- **Given:** an anchor of Jan 31 2027, monthly every 1, fixed, with "today" of Apr 15 2027
- **When:** the next date is computed
- **Then:** the result is Apr 30 2027 (first occurrence strictly after today, day-of-month preserved where the month allows, no accumulated drift to day 28)

### Recurrence — long-overdue catch-up through the API
- **Given:** an open daily-fixed task with due_date today-30
- **When:** PATCH status done
- **Then:** exactly one successor exists with due_date today+1 (no backlog of past occurrences)

### Recurrence — fixed result equal to today is pushed forward
- **Given:** an open weekly-fixed task, interval 1, due_date today-7
- **When:** PATCH status done
- **Then:** the successor's due_date is today+7

### Recurrence — after_completion uses completion date
- **Given:** an open weekly after_completion task, interval 1, due_date today-10
- **When:** PATCH status done
- **Then:** the successor's due_date is today+7

### Recurrence — after_completion with no dates
- **Given:** an open daily after_completion task with no dates
- **When:** PATCH status done
- **Then:** the successor's due_date is today+1

### Recurrence — every freq and mode combination yields exactly one successor
- **Given:** open tasks for each of daily, weekly, monthly crossed with fixed and after_completion, each with a due_date
- **When:** each is completed
- **Then:** for each, exactly one successor exists, with status open, a due_date after today, and the same recurrence settings

### Recurrence — successor copies content and resets completion fields
- **Given:** a recurring open task with description, priority high, effort_hours 2.5, a parent_task_id, and a done-time actual_duration_minutes of 40 set in the completing request
- **When:** PATCH status done
- **Then:** the successor has the same title, description, priority, effort_hours, parent_task_id and recurrence settings; status open; completed_at null; actual_duration_minutes null; recurrence_next_id null

### Recurrence — labels copied to successor
- **Given:** a recurring task with labels "home" and "chores" in LabelEngine
- **When:** PATCH status done
- **Then:** LabelEngine receives attach requests for "home" and "chores" on the successor id with object type task

### Recurrence — label copy failure does not fail completion
- **Given:** a recurring task and LabelEngine unreachable
- **When:** PATCH status done
- **Then:** the PATCH returns 200, the source is done, and the successor exists

### Recurrence — undo and redo spawn no duplicate
- **Given:** a recurring task that was completed once (one successor exists)
- **When:** PATCH status open, then PATCH status done again
- **Then:** the total number of tasks with that title is still two (source and the single successor) and recurrence_next_id is unchanged

### Recurrence — repeated done does not respawn
- **Given:** a recurring task already done with a successor
- **When:** PATCH status done again
- **Then:** no new task is created and the response has recurrence_next_date null

### Recurrence — non-recurring completion spawns nothing
- **Given:** a non-recurring open task
- **When:** PATCH status done
- **Then:** no new task is created and the response has recurrence_next_date null

### Recurrence — clearing recurrence while completing spawns nothing
- **Given:** a recurring open task
- **When:** PATCH with status done and recurrence_freq null in the same request
- **Then:** no successor is created and the task has recurrence_freq null

### Recurrence — scheduled recurring task spawns scheduled successor with blocker
- **Given:** a scheduled task at scheduled_at today+2, due_date today+4, weekly every 1, fixed, and CalendarConnector configured
- **When:** PATCH status done
- **Then:** the successor has status scheduled, scheduled_at today+9, due_date today+11; a calendar delete is requested for the source and a calendar create is requested for the successor with title prefixed "[Atlas] " and the all-day date today+9

### Recurrence — scheduled task completed through the edit-form payload
- **Given:** a scheduled recurring fixed task with scheduled_at today+1 and no due_date
- **When:** PATCH with status done, scheduled_at null, due_date null, and the unchanged recurrence fields (as the edit form sends them)
- **Then:** the PATCH succeeds (no date-required error) and the successor is scheduled with scheduled_at one interval after the original scheduled_at

### Recurrence — calendar failure does not fail completion
- **Given:** a scheduled recurring task and a CalendarConnector returning errors
- **When:** PATCH status done
- **Then:** the PATCH returns 200 and the successor exists

### Recurrence — spawn is atomic
- **Given:** a recurring open task and a forced failure while inserting the successor
- **When:** PATCH status done
- **Then:** the response is an error, the source is still not done, and no successor and no recurrence_next_id exist

### Recurrence — deleting the successor clears the pointer
- **Given:** a completed recurring task with a successor
- **When:** DELETE the successor
- **Then:** the source's recurrence_next_id is null

### Recurrence — successor appears in the agenda when due soon
- **Given:** an open daily-fixed task due today
- **When:** PATCH status done, then GET the agenda
- **Then:** the source is absent and the successor is present with agenda_bucket "upcoming" and agenda_date today+1

### [UI] Today is the default landing tab
- **Given:** the user opens the Tasks app at /tasks
- **When:** the page loads
- **Then:** the first tab "Today" is selected and shows the agenda; "Active" is available as a separate tab at /tasks/active

### [UI] Today sections and effort totals
- **Given:** an overdue task (1 h), two tasks due today (1 h and no effort), and tasks due tomorrow (2 h) and in three days (0.5 h)
- **When:** the user views the Today tab
- **Then:** sections appear in order Overdue, Today, Next 7 days; the Today header shows 1 h; the tomorrow and three-days-ahead day headers show 2 h and 0.5 h respectively; the overdue row displays its date

### [UI] Today empty state
- **Given:** no dated tasks in the window
- **When:** the user views the Today tab
- **Then:** an empty-state message is shown and no section headers are rendered

### [UI] Completing a task updates the list in place
- **Given:** the Today tab with a task due today
- **When:** the user presses the complete button on that row
- **Then:** the row disappears without a full-page loading skeleton and other rows remain

### [UI] Label filter applies to Today
- **Given:** tasks due today with different labels and a label filter that selects only one label
- **When:** the user views the Today tab
- **Then:** only tasks carrying a selected label are listed and the section effort totals reflect only the listed rows

### [UI] Repeat control on create
- **Given:** the create panel
- **When:** the user chooses Weekly, sets interval 2, ticks "From completion date" and creates the task
- **Then:** the task appears with a repeat icon whose tooltip reads "Every 2 weeks, after completion"

### [UI] Repeat control hides interval when none
- **Given:** the create panel with Repeat set to None
- **When:** the user views the Repeat control
- **Then:** no interval input and no "From completion date" toggle are shown

### [UI] Repeat control edit and clear
- **Given:** an existing recurring task opened in the edit form
- **When:** the user sees the form, then sets Repeat to None and saves
- **Then:** the form first shows the current frequency, interval and toggle state; after saving, the task no longer shows a repeat icon

### [UI] Next-date toast on completing a recurring task
- **Given:** a recurring task visible in any tab
- **When:** the user completes it
- **Then:** a toast "Next: <date>" showing the successor's date appears and dismisses on its own; completing a non-recurring task shows no toast

### [UI] Recurring task row shows repeat indicator
- **Given:** a recurring and a non-recurring task in the Active tab
- **When:** the user views the list
- **Then:** only the recurring row shows the repeat icon, and opening it shows the recurrence label in the edit view
