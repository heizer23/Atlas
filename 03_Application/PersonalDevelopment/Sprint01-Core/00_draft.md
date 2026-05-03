Sprint Draft — Learning Tile (TaskTracker Extension)
Objective

Introduce a Learning tile as a dedicated UI surface for personal development, backed by TaskTracker.

Enable structured learning workflows using:

task types
hierarchical relationships
markdown-defined potential subtasks
progress visualization

The system must remain lean and reuse existing components.

Core Concept

Users define training units as logical parent tasks and specify future work as markdown lines.

Only when a user decides to act, a line is promoted into a real task.

Planned work = markdown
Committed work = task object
Pre-Checks (MANDATORY)
Schema check
Confirm completed_at does NOT exist
Add completed_at field
Hierarchy decision
Evaluate if LinkingEngine can support:
parent → children queries
aggregation (max completed_at, counts)
If complex:
introduce parent_task_id
document as controlled deviation
Data Model Changes (TaskTracker)

Extend task:

task_type text not null default 'normal'
parent_task_id uuid null        (ONLY if LinkingEngine not used)
actual_duration_minutes integer null
completed_at timestamp null
Task Types
normal
training_unit
training_session
training_unit = logical container (not actionable)
training_session = executable work
Markdown Contract — Potential Subtasks
Location
## Potential Subtasks
Format
- [ ] <task title>

Example:

## Potential Subtasks

- [ ] IBP800 Unit 1 Session 1
- [ ] IBP800 Unit 1 Session 2
Activated State
- [x] IBP800 Unit 1 Session 1 → task: <uuid>
Behavior — Subtask Activation

For each unchecked line:

UI shows: Create task

On click:

Create Task:

title = line text
task_type = training_session
parent = training_unit
labels = inherited from parent
status = open

Then update markdown:

mark as checked
append → task: <uuid>
Views
1. Main Task View (existing)

Include:

normal
training_session

Exclude:

training_unit
2. Learning Tile (NEW)

Separate UI tile (same level as Tasks, Food, Workout)

Data Source
task_type = training_unit
+ existing label filter
Sorting
DONE units:
- first
- sorted by last_child_completed_at DESC

OPEN units:
- after
- sorted by priority DESC
Derived Fields
last_child_completed_at =
max(child.completed_at)

progress =
completed_child_count / total_child_count
UI Behavior (Learning Tile)

Each training unit displays:

- title
- labels
- priority
- progress
- last activity date
- potential subtasks (parsed markdown)
- active child tasks

Actions:

- Create task from potential subtask
- Open child tasks
- Update duration on child tasks
Execution Tracking

For training_session tasks:

actual_duration_minutes = user-maintained
completed_at = set when status = done

No separate session object.

Frontend Architecture
Learning is a separate tile/application entry
Registered in Atlas Shell navigation
Consumes TaskTracker APIs
Does NOT introduce a new backend service
Design Constraints
No LearningGoal object
No LearningMean object
No LearningSession object
No new platform components
No over-generalized hierarchy system
Design Principles
Only create objects for real commitments
Keep future work in markdown
Labels define meaning
Task types define behavior
Reuse existing components
Keep system LLM-legible
Acceptance Criteria
User can create training_unit tasks
Markdown subtasks are parsed correctly
User can create tasks from markdown lines
Created tasks are linked to parent
Markdown is updated after activation
Main task view excludes training_unit
Learning tile is visible in navigation
Learning tile displays training units correctly
Progress is correctly calculated
Sorting rules are correctly applied
Label filter works as in TaskTracker