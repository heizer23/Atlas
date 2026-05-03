# Test Spec — PersonalDevelopment — Sprint01-Core

## Scope
Tests cover: the new GET /api/tasks/training-units endpoint in TaskTracker, the training_unit exclusion on GET /api/tasks, the new task_type/parent_task_id fields on POST and PATCH /api/tasks, the server-side completed_at assignment, and the markdownSubtasks parsing/update logic. Out of scope: Playwright UI tests (deferred), label inheritance end-to-end, and PreferenceStore integration for the Learning label filter.

---

## Scenarios

### Training Units — Empty Result
- **Given:** No tasks with task_type = training_unit exist in the database
- **When:** GET /api/tasks/training-units
- **Then:** Returns Dataset with rows = [], total = 0, no error

### Training Units — Single Unit No Children
- **Given:** One task with task_type = training_unit (id=fix-unit-1), status=open, and no child tasks
- **When:** GET /api/tasks/training-units
- **Then:** Returns Dataset with one row where completed_child_count = 0, total_child_count = 0, last_child_completed_at = null

### Training Units — Unit With Mixed Children
- **Given:** Task fix-unit-1 (training_unit, status=open) has two child tasks: fix-child-1 (training_session, status=done, completed_at=2026-04-01T10:00:00Z) and fix-child-2 (training_session, status=open)
- **When:** GET /api/tasks/training-units
- **Then:** Row for fix-unit-1 has completed_child_count = 1, total_child_count = 2, last_child_completed_at = '2026-04-01T10:00:00Z'

### Training Units — Sort Order: Done Before Open, Then By Priority
- **Given:** Three training_unit tasks: fix-unit-done (status=done, last_child_completed_at=2026-04-10), fix-unit-open-high (status=open, priority=high), fix-unit-open-low (status=open, priority=low)
- **When:** GET /api/tasks/training-units
- **Then:** Response rows in order: fix-unit-done, fix-unit-open-high, fix-unit-open-low

### Training Units — Labels Embedded
- **Given:** Task fix-unit-1 (training_unit) has two labels attached via LabelEngine: 'python', 'algorithms'
- **When:** GET /api/tasks/training-units
- **Then:** Row for fix-unit-1 includes labels = [{id: ..., name: 'python'}, {id: ..., name: 'algorithms'}]

### Main Task List Excludes Training Units
- **Given:** Tasks exist: fix-normal-1 (task_type=normal), fix-session-1 (task_type=training_session), fix-unit-1 (task_type=training_unit)
- **When:** GET /api/tasks (no filters)
- **Then:** Response rows contain fix-normal-1 and fix-session-1; fix-unit-1 is absent

### Main Task List Excludes Training Units — Active View
- **Given:** fix-unit-1 (task_type=training_unit, status=open) exists
- **When:** GET /api/tasks?view=active
- **Then:** fix-unit-1 is absent from the response

### Create Training Unit Task
- **Given:** No pre-existing tasks
- **When:** POST /api/tasks with body {title: 'Learn Python', task_type: 'training_unit', status: 'open', priority: 'high'}
- **Then:** Returns Dataset (single row) with task_type = 'training_unit', id is a UUID, status = 'open'

### Create Training Session With Parent
- **Given:** Task fix-unit-1 (training_unit) exists
- **When:** POST /api/tasks with body {title: 'Session 1', task_type: 'training_session', parent_task_id: 'fix-unit-1', status: 'open', priority: 'medium'}
- **Then:** Returns Dataset (single row) with task_type = 'training_session', parent_task_id = 'fix-unit-1'

### PATCH — completed_at Set Server-Side On Done Transition
- **Given:** Task fix-session-1 (training_session, status=open, completed_at=null) exists
- **When:** PATCH /api/tasks/fix-session-1 with body {status: 'done'}
- **Then:** Response row has status = 'done' and completed_at is a non-null ISO timestamp

### PATCH — completed_at Not Overwritten If Already Set
- **Given:** Task fix-session-1 (training_session, status=done, completed_at=2026-04-01T10:00:00Z) exists
- **When:** PATCH /api/tasks/fix-session-1 with body {title: 'Updated title'}
- **Then:** Response row has completed_at = '2026-04-01T10:00:00Z' unchanged

### PATCH — completed_at Not Set When Transitioning To Non-Done Status
- **Given:** Task fix-session-1 (training_session, status=open, completed_at=null) exists
- **When:** PATCH /api/tasks/fix-session-1 with body {status: 'in_progress'}
- **Then:** Response row has completed_at = null

### PATCH — actual_duration_minutes Update
- **Given:** Task fix-session-1 (training_session) exists with actual_duration_minutes = null
- **When:** PATCH /api/tasks/fix-session-1 with body {actual_duration_minutes: 45}
- **Then:** Response row has actual_duration_minutes = 45

### Markdown Parsing — Section Absent
- **Given:** description = 'A training unit with no subtasks section'
- **When:** parseSubtasks(description) is called
- **Then:** Returns {unchecked: [], activated: []}

### Markdown Parsing — Unchecked Lines
- **Given:** description contains '## Potential Subtasks\n- [ ] Session 1\n- [ ] Session 2'
- **When:** parseSubtasks(description) is called
- **Then:** Returns {unchecked: [{lineText: 'Session 1'}, {lineText: 'Session 2'}], activated: []}

### Markdown Parsing — Mixed Checked And Unchecked
- **Given:** description contains '## Potential Subtasks\n- [x] Session 1 → task: abc-123\n- [ ] Session 2'
- **When:** parseSubtasks(description) is called
- **Then:** Returns {unchecked: [{lineText: 'Session 2'}], activated: [{lineText: 'Session 1', taskId: 'abc-123'}]}

### Markdown Parsing — Empty Section
- **Given:** description = '## Potential Subtasks\n\nNo lines below'
- **When:** parseSubtasks(description) is called
- **Then:** Returns {unchecked: [], activated: []}

### Markdown Update — Activate A Line
- **Given:** description = 'Intro\n\n## Potential Subtasks\n- [ ] Session 1\n- [ ] Session 2'
- **When:** activateSubtaskLine(description, 'Session 1', 'new-uuid-123') is called
- **Then:** Returns description with '- [ ] Session 1' replaced by '- [x] Session 1 → task: new-uuid-123' and '- [ ] Session 2' unchanged

### Markdown Update — Line Not Found Is No-Op
- **Given:** description = '## Potential Subtasks\n- [ ] Session 1'
- **When:** activateSubtaskLine(description, 'Session 99', 'some-uuid') is called
- **Then:** Returns description unchanged

### [UI — manual] Learning Tile Visible In Navigation
- **Given:** Atlas Shell is running with the PersonalDevelopment shellConfig registered
- **When:** User opens the Atlas Shell
- **Then:** 'Learning' appears in the bottom navigation (mobile) and sidebar (desktop)

### [UI — manual] Learning Page Shows Training Units
- **Given:** At least one training_unit task exists (fix-unit-1, title='Learn Python', 1 of 2 sessions done)
- **When:** User navigates to /learning
- **Then:** A card shows 'Learn Python', a progress indicator showing 1/2, and the last activity date

### [UI — manual] Subtask Activation Creates Task And Updates Markdown
- **Given:** fix-unit-1 has description '## Potential Subtasks\n- [ ] Session 1'
- **When:** User opens the unit detail and clicks 'Create task' next to 'Session 1'
- **Then:** A new task appears in the child task list; the line shows as checked with a task reference; no unchecked line remains for 'Session 1'
