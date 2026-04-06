Atals Linking Engine v1 Spec
1. Purpose

The goal of the linking engine is to allow users to create structured relationships between objects in Atals.

Version 1 focuses on a narrow but reusable first use case:

link one task to another task
prepare the system so the same mechanism can later support workouts, meals, emails, calendar events, and other objects

The first visible product use case is:

from a task, create a link to another task
display linked tasks on the task detail screen, grouped by link type

Example:

Task: Clean House
Linked Tasks
SubTasks

Clean Kitchen
Clean Bedroom
2. Scope for v1
Included
object linking for:
task → task
groundwork for task → workout and task → meal
link creation from the task UI
fuzzy search for target object
selectable link type with autocomplete suggestions
display of linked objects on task detail page
canonical relation storage
support for directional and non-directional relations
Not included
AI-generated links
email integration
automatic link suggestions
advanced graph navigation
editing relation definitions in admin UI
semantic/vector search
link visibility outside detail page
workflow logic triggered by links
3. Product principles
3.1 Generic engine, narrow launch

Even though v1 only exposes task linking, the backend model must be generic enough to support all object types later.

3.2 Controlled vocabulary in storage

The UI may allow near-free-text input with suggestions, but the backend stores normalized relation keys.

This avoids duplicates like:

subtask
sub task
SubTask
child task
3.3 Human-friendly display

Stored relation names and displayed relation names may differ.

Example:

stored: subtask_of
on child task: show Parent Task
on parent task: show SubTasks
3.4 Provenance by default

Every link must record who created it and when.

3.5 One canonical direction

Each relation is stored in exactly one canonical direction, even if the UI shows its inverse on some screens.

4. Supported object types in v1

The engine should support these object types structurally:

task
workout
meal

The initial UI only needs to expose task linking in the task context menu.

5. User stories
5.1 Create a subtask link

As a user viewing task “Clean House”, I want to link “Clean Kitchen” as a subtask so I can organize work hierarchically.

5.2 Create a related task link

As a user viewing task “Clean House”, I want to link “Buy Cleaning Supplies” as related so I can keep connected work visible.

5.3 View linked tasks

As a user viewing a task detail screen, I want to see all linked tasks grouped by relation type.

5.4 Search target object

As a user creating a link, I want to search for the target task by name using fuzzy search.

6. UX specification
6.1 Entry point

On the task context menu, add:

Mark Complete
Delete
Link

Clicking Link opens a modal or pop-up.

6.2 Link creation modal
Fields
Source object

Read-only, implicit from current context.

Example:

Source: Clean House
Target object type

Dropdown with:

Tasks
Workouts
Meals

Default:

Tasks
Target object search

Search box with fuzzy search inside the selected object type.

Requirements:

search by title/name
exclude current source object from results
show a short result list
selecting a result fills the target object
Link type

Text input with autocomplete suggestions.

For v1 task-to-task suggestions:

SubTask
Related To

Optional later suggestions:

Depends On
Blocks
Duplicate Of

Behavior:

user can type freely
system attempts normalization to a known canonical relation
if no valid canonical relation is found, save should be blocked in v1
Save action

Button: Create Link

6.3 Link creation behavior

When creating a link:

user chooses target object type
user searches and selects target object
user chooses link type
system normalizes relation
system stores canonical edge
task detail screen reflects the new link
6.4 Detail screen display

On task detail page, add section:

Linked Objects

Grouped by display label.

Example:

Linked Tasks

SubTasks

Clean Kitchen
Clean Bedroom

Related Tasks

Buy Cleaning Supplies

Display requirements:

group by relation type
show linked object title
clicking linked object opens its detail page
group ordering should follow configured relation priority
object ordering inside group should default to created time ascending or title ascending
7. Relation model
7.1 Canonical relation keys for v1
subtask_of

Meaning:
child task points to parent task

Canonical example:

Clean Kitchen subtask_of Clean House

UI rendering:

on Clean Kitchen: Parent Task → Clean House
on Clean House: SubTasks → Clean Kitchen

Direction:

directional

Allowed types:

task → task
related_to

Meaning:
two objects are generally related

Canonical example:

Buy Cleaning Supplies related_to Clean House

Direction:

non-directional conceptually, but stored once in a canonical ordered form

Allowed types:

task ↔ task
can later support task ↔ workout, task ↔ meal, etc.

UI rendering:

Related Tasks
7.2 Future relations, not required for first launch
depends_on
blocks
duplicate_of

These should not be fully exposed unless needed, but schema should allow them.

8. Direction rules
8.1 Directional relations

Some relations have semantic direction.

Example:

child task subtask_of parent task

These must be stored only in the configured canonical direction.

8.2 Non-directional relations

Some relations are symmetric.

Example:

task A related_to task B

For storage consistency, non-directional relations must still be stored once only.

Recommended rule:

store using lexical or numeric ordering of object IDs
smallest object ID becomes from_object_id
largest becomes to_object_id

This prevents duplicate mirrored rows.

9. Data model
9.1 objects

Canonical registry of all linkable objects.

Fields
id UUID / primary key
workspace_id
type enum
task
workout
meal
status optional
created_at
updated_at

Notes:

type-specific data remains in type-specific tables
this table exists to provide universal link targets
9.2 Type-specific tables
tasks
object_id FK to objects.id
title
description
completed_at
created_at
updated_at
workouts
object_id
relevant workout fields
meals
object_id
relevant meal fields
9.3 relation_definitions

Configuration table for canonical relations.

Fields
key primary key
forward_label
reverse_label
is_directional boolean
allowed_from_types json/array
allowed_to_types json/array
is_active boolean
sort_order integer
Example rows
subtask_of
key: subtask_of
forward_label: Parent Task
reverse_label: SubTasks
is_directional: true
allowed_from_types: ["task"]
allowed_to_types: ["task"]
related_to
key: related_to
forward_label: Related Tasks
reverse_label: Related Tasks
is_directional: false
allowed_from_types: ["task", "workout", "meal"]
allowed_to_types: ["task", "workout", "meal"]
9.4 object_links

Stores the actual links between objects.

Fields
id UUID / primary key
workspace_id
from_object_id FK to objects.id
to_object_id FK to objects.id
relation_key FK to relation_definitions.key
created_by_type enum
user
system
agent
sync_job
rule
created_by_id string nullable
confidence numeric default 1.0
source_run_id string nullable
metadata_json json default {}
created_at
archived_at nullable
v1 defaults

For manual links:

created_by_type = user
created_by_id = current_user_id
confidence = 1.0
source_run_id = null
metadata_json = {}
10. Constraints and validation
10.1 General rules
source and target object must exist
source and target must belong to same workspace
self-links are not allowed
relation key must exist in relation_definitions
relation must be valid for object type pair
archived objects cannot be linked unless explicitly supported later
10.2 Duplicate prevention

The system must prevent duplicate active links.

For directional relations:

unique on (workspace_id, from_object_id, to_object_id, relation_key, archived_at is null)

For non-directional relations:

store in canonical object ID order
unique on (workspace_id, from_object_id, to_object_id, relation_key, archived_at is null)
10.3 Relation-specific rules
subtask_of
both objects must be tasks
source is child, target is parent
cycles should be prevented if feasible in v1
at minimum, direct reverse cycle must be prevented
ideal: full ancestor cycle prevention

Example invalid:

A subtask_of B
B subtask_of A
11. API specification
11.1 Create link
Endpoint

POST /object-links

Request
{
  "source_object_id": "obj_clean_kitchen",
  "target_object_id": "obj_clean_house",
  "relation_input": "SubTask"
}
Server behavior
resolve both objects
determine their types
normalize relation_input to canonical relation_key
validate allowed pair
apply canonical direction rules
create row in object_links
Example stored result
{
  "id": "link_123",
  "from_object_id": "obj_clean_kitchen",
  "to_object_id": "obj_clean_house",
  "relation_key": "subtask_of",
  "created_by_type": "user",
  "created_by_id": "user_42",
  "confidence": 1.0,
  "metadata_json": {},
  "created_at": "2026-04-06T10:15:00Z"
}
11.2 Search linkable objects
Endpoint

GET /objects/search

Query params
type
q
exclude_object_id
limit
Example

GET /objects/search?type=task&q=clean&exclude_object_id=obj_clean_house&limit=10

Behavior
fuzzy search by title/name
scoped to workspace
returns lightweight object result set
11.3 Get task links for detail screen
Endpoint

GET /tasks/{task_id}/links

Response shape

Grouped and presentation-ready.

Example:

{
  "task_id": "obj_clean_house",
  "groups": [
    {
      "group_key": "subtasks",
      "label": "SubTasks",
      "items": [
        { "object_id": "obj_clean_kitchen", "type": "task", "title": "Clean Kitchen" },
        { "object_id": "obj_clean_bedroom", "type": "task", "title": "Clean Bedroom" }
      ]
    },
    {
      "group_key": "related_tasks",
      "label": "Related Tasks",
      "items": [
        { "object_id": "obj_buy_supplies", "type": "task", "title": "Buy Cleaning Supplies" }
      ]
    }
  ]
}

The server should resolve inverse labels correctly based on current object position in the link.

11.4 Archive/delete link
Endpoint

DELETE /object-links/{link_id}

Recommended implementation:

soft delete by setting archived_at
do not hard delete initially
12. Normalization rules for relation input

User-facing input may vary. Backend maps it to canonical keys.

Examples
subtask → subtask_of
sub task → subtask_of
child task → subtask_of
related → related_to
related to → related_to

If input does not map to a known relation:

return validation error in v1

Reason:

keep storage vocabulary clean from the start
13. Display logic
13.1 Group generation

When showing links on a task detail screen:

fetch all active links where task appears as either from_object_id or to_object_id
for each link, determine whether current object is on forward or reverse side
choose display label accordingly
resolve target object as “the other object”
group by display label / logical group key
13.2 Example

Stored links:

Clean Kitchen subtask_of Clean House
Clean Bedroom subtask_of Clean House
Buy Cleaning Supplies related_to Clean House

On Clean House detail screen:

show reverse label for subtask_of → SubTasks
show other side object names

Result:

SubTasks: Clean Kitchen, Clean Bedroom
Related Tasks: Buy Cleaning Supplies

On Clean Kitchen detail screen:

show forward label for subtask_of → Parent Task
item: Clean House
14. Search behavior
14.1 Requirements
fuzzy search by title/name
scoped to selected object type
scoped to current workspace
exclude current source object
limit result count for fast UI response
14.2 Nice-to-have, not required
recent objects ranking boost
exact title match boost
keyboard navigation in results
15. Permissions
15.1 Create link

User must have access to both source and target objects.

15.2 View link

User must have access to current object and linked object to see the connection.

If permission models later become complex, hidden targets should not leak titles through link rendering.

16. Audit and provenance

Every link row must preserve:

creator type
creator ID
creation timestamp
optional metadata

This enables:

debugging
trust differentiation
future machine-generated link support

For v1 manual links, confidence is always 1.0.

17. Error states

The UI and API must handle these errors:

target object not found
self-link not allowed
invalid relation for selected object types
duplicate link already exists
relation input not recognized
insufficient permissions
cycle not allowed for hierarchical relation

Suggested user-facing messages:

“You cannot link an item to itself.”
“This link already exists.”
“This link type is not valid for these object types.”
“Please choose one of the suggested link types.”
18. Non-functional requirements
Performance
link creation should feel instant
search should return within normal UI latency for small/medium workspaces
task detail page should load linked objects in one query path
Reliability
duplicate prevention at DB level
relation normalization on backend, not only frontend
Extensibility

Must support later addition of:

Gmail messages
calendar events
notes
contacts
AI-extracted entities
machine-created links
provenance metadata
semantic retrieval layer
19. Seed data for v1

Seed relation_definitions with:

1. subtask_of
forward_label: Parent Task
reverse_label: SubTasks
is_directional: true
allowed_from_types: ["task"]
allowed_to_types: ["task"]
sort_order: 10
2. related_to
forward_label: Related Tasks
reverse_label: Related Tasks
is_directional: false
allowed_from_types: ["task", "workout", "meal"]
allowed_to_types: ["task", "workout", "meal"]
sort_order: 20
20. Acceptance criteria

The feature is complete for v1 when all of the following are true:

A user can open a task and click Link.
A modal appears with:
object type dropdown
target object search
link type input with suggestions
The user can select another task and create a SubTask link.
The backend stores the link in canonical normalized form.
The parent task detail page shows the child task under SubTasks.
The child task detail page shows the parent task under Parent Task.
The user can create a Related To link between tasks.
Duplicate links are prevented.
Self-links are prevented.
Relation keys in storage remain normalized and controlled.
21. Example end-to-end scenario

Objects:

Clean House
Clean Kitchen
Clean Bedroom
Buy Cleaning Supplies

User actions:

from Clean House, link Clean Kitchen as SubTask
from Clean House, link Clean Bedroom as SubTask
from Clean House, link Buy Cleaning Supplies as Related To

Stored links:

Clean Kitchen subtask_of Clean House
Clean Bedroom subtask_of Clean House
Buy Cleaning Supplies related_to Clean House

Rendered on Clean House:

SubTasks
Clean Kitchen
Clean Bedroom
Related Tasks
Buy Cleaning Supplies

Rendered on Clean Kitchen:

Parent Task
Clean House
22. Recommended implementation order
Phase 1
create objects
create relation_definitions
create object_links
seed canonical relations
Phase 2
implement object search endpoint
implement link creation endpoint
implement duplicate prevention and validation
Phase 3
add Link button and modal on task UI
render linked objects on task detail page
Phase 4
add cycle prevention for subtask_of
prepare support for task ↔ workout and task ↔ meal
23. Open questions for later, not blocking v1
Should users be allowed to define custom relation types?
Should subtasks affect progress calculation?
Should the same popup eventually be reusable from workouts and meals?
Should links support notes/comments?
Should links have statuses like suggested, confirmed, rejected?
Should drag-and-drop hierarchy later create subtask_of links?