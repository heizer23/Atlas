Atals Labeling v1 — Minimal Slice
1. Goal

Enable users to quickly classify tasks using labels and use those labels to group tasks in the list view.

This is a lightweight, fast system:

no hierarchy
no metadata overhead
no complex rules

Example:

Label: Outside
All tasks requiring being outside are grouped together
2. Scope
Included
labels attachable to any object (via objects.id)
UI support for tasks only
assign/remove labels from:
task detail view
task list (three-dot menu)
label creation during assignment
task list grouped by label
Not included
label hierarchy
label priority
label colors (optional, can be added later)
filtering UI
label management screen
labels on workouts/meals in UI (data model supports it)
3. Data Model (Minimal)
3.1 labels
labels
- id
- name
Notes
no normalization field
no metadata
duplicates are allowed unless you choose to block exact matches
3.2 object_labels
object_labels
- object_id
- label_id
Constraints
unique (object_id, label_id) to prevent duplicates
Assumption
object_id references your universal objects.id

This keeps labels compatible with your linking engine.

4. Core Behavior
4.1 Labels are many-to-many
one task can have multiple labels
one label can apply to many tasks
4.2 Labels are optional

Tasks may have:

zero labels → appear in Unlabeled
one label → grouped under that label
multiple labels → grouped by primary label rule
5. Primary Label Rule (important)

Since tasks can have multiple labels, we need a deterministic grouping rule.

v1 Rule:

The first attached label is the grouping label

Example:

Task:

Pick up package
Labels:
Outside
Errand

→ appears under:

Outside

→ displays:

Outside, Errand

This keeps logic simple and stable.

6. UX Specification
6.1 Task Detail View

Add section:

Labels

Behavior
show current labels as chips
button: + Add label
clicking opens label picker
user can:
select existing label
type new label → create instantly
labels removable via chip “x”
6.2 Task List (Three-Dot Menu)

Add action:

Set Labels
Behavior
opens compact label picker
shows current labels
allows:
add label
remove label
no navigation to detail view needed

This is key for fast workflows.

6.3 Label Picker

Shared component used in both places.

Behavior
text input with live search
shows matching existing labels
selecting adds label
if no match:
option: Create "X"
immediate feedback (no heavy modal required)
Example

User types: out

→ suggestions:

Outside

User types: garden (not existing)

→ option:

Create "garden"
7. Task List Grouping
7.1 Grouped by label

Tasks are displayed in sections:

Example:

Outside

Buy seeds
Clean balcony

Home

Clean kitchen

Unlabeled

Reply to Anna
7.2 Ordering of groups

For v1:

alphabetical by label name
Unlabeled always last
7.3 Task ordering within group

Simple default:

by creation time or
by manual order if you already support it

(No need to overdesign here)

8. API Slice
8.1 Search labels

GET /labels?q=out

Returns:

[
  { "id": "lbl1", "name": "Outside" }
]
8.2 Create label

POST /labels

{
  "name": "Outside"
}
8.3 Attach label

POST /objects/{object_id}/labels

{
  "label_name": "Outside"
}
Server behavior
search existing label by name
if found → reuse
if not → create
attach to object
ignore duplicate (object_id, label_id)
8.4 Remove label

DELETE /objects/{object_id}/labels/{label_id}

8.5 Get labels for task

GET /tasks/{task_id}/labels

8.6 Task list grouped by label

GET /tasks?group_by=label

Response:

{
  "groups": [
    {
      "label": "Outside",
      "items": [
        { "id": "t1", "title": "Buy seeds", "labels": ["Outside"] },
        { "id": "t2", "title": "Pick up package", "labels": ["Outside", "Errand"] }
      ]
    },
    {
      "label": "Unlabeled",
      "items": [
        { "id": "t3", "title": "Reply to Anna", "labels": [] }
      ]
    }
  ]
}
9. Validation Rules
label name must not be empty
duplicate (object_id, label_id) not allowed
object must exist
label must exist (or be created inline)
10. Example End-to-End
Labels created
Outside
Home
Errand
Tasks
Buy seeds → Outside
Clean kitchen → Home
Pick up package → Outside, Errand
Reply to Anna → none
Task list

Home

Clean kitchen

Outside

Buy seeds
Pick up package

Unlabeled

Reply to Anna
11. Acceptance Criteria
User can add labels in task detail view
User can add/remove labels from task list menu
Labels can be created inline
Labels are reusable across tasks
Tasks can have multiple labels
Tasks are grouped by label in list view
Unlabeled tasks appear in a separate group
Duplicate label assignment is prevented
System remains fast and simple
12. Implementation Order
Phase 1
create labels
create object_labels
Phase 2
implement label attach/remove endpoints
implement label search
Phase 3
build label picker component
Phase 4
integrate into:
task detail view
task list menu
Phase 5
implement grouped task list
13. Key Design Decision Recap
labels are not links
labels are simple and fast
no normalization layer
no metadata overhead
grouping uses first label
architecture supports future expansion