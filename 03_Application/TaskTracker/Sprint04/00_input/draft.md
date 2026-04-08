Task Optimizations Slice
1. Changes

We add four decisions:

Get-all-tasks API includes labels
Task overview list is sorted/grouped by labels
Mark Complete becomes a direct button, not hidden in the three-dot menu
New task form in detail screen preselects priority = Medium
2. API change: tasks must include labels

Since OpenClaw needs labels, the task list endpoint should return them directly.

Decision

GET /tasks returns each task with its labels included.

Example response:

{
  "groups": [
    {
      "label": "Outside",
      "items": [
        {
          "id": "t1",
          "title": "Buy seeds",
          "priority": "medium",
          "completed": false,
          "labels": [
            { "id": "l1", "name": "Outside" }
          ]
        },
        {
          "id": "t2",
          "title": "Pick up package",
          "priority": "high",
          "completed": false,
          "labels": [
            { "id": "l1", "name": "Outside" },
            { "id": "l2", "name": "Errand" }
          ]
        }
      ]
    }
  ]
}
Why

This avoids:

extra label lookup calls
UI stitching work
OpenClaw having incomplete task context

So labels should not require a second fetch.

3. Task overview sorting/grouping by labels

This should now be a fixed behavior for the overview list.

Decision

The task overview is grouped by label.

Grouping rule
use the task’s first attached label as the primary grouping label
if no label exists, group under Unlabeled
Group order
alphabetical by label name
Unlabeled last
Task row display

Even though grouping uses one primary label, each task row still shows all labels.

Example:

Outside

Buy seeds [Outside]
Pick up package [Outside] [Errand]

Unlabeled

Reply to Max

This matches your earlier direction and makes labels immediately useful.

4. Mark Complete button

Agreed. This should be promoted out of the three-dot menu.

Decision

Each task row shows a visible Mark Complete button.

Not inside:

three-dot menu

Still inside three-dot menu:

Set Labels
Delete
other secondary actions
Why

Marking complete is a primary action, not a secondary one.

That means:

faster task processing
better visibility
fewer clicks

A good row action layout would be:

task title / labels
Mark Complete button
three-dot menu for secondary actions

If completion state is toggle-based, the button can become:

Complete for open tasks
Completed or disabled state for completed tasks

But the key point is: visible and immediate.

5. New task default priority

Also agreed.

Decision

When creating a new task from the detail screen, the priority field defaults to:

Medium

This applies unless:

task creation is invoked from a context that explicitly supplies a priority
Why

Medium is the safest neutral default:

avoids accidental overload of high-priority tasks
avoids burying tasks as low priority
reduces form friction
6. Spec updates
6.1 Task list endpoint

Update GET /tasks contract so every task object includes:

labels
priority
completed or equivalent status field

Minimum task shape:

{
  "id": "t1",
  "title": "Buy seeds",
  "priority": "medium",
  "completed": false,
  "labels": [
    { "id": "l1", "name": "Outside" }
  ]
}
6.2 Overview screen behavior

Task overview screen should:

group by primary label
show all labels on each row
place unlabeled tasks in Unlabeled
expose Mark Complete directly on the row
6.3 New task form

Task creation form in detail screen:

preselect priority = medium
7. Acceptance criteria

This optimization slice is done when:

GET /tasks returns labels for every task
OpenClaw can read task labels from the task payload directly
Task overview is grouped by label
Tasks with no labels appear under Unlabeled
Task rows display all assigned labels
Mark Complete is visible directly on the task row
Mark Complete is no longer hidden as the primary path inside the three-dot menu
New tasks created from the detail screen default to medium priority