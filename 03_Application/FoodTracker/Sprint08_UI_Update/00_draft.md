Sprint Draft — FoodTracker Date Handling & UI Fixes
Objective

Fix incorrect date handling and improve usability in FoodTracker:

Respect selected date when logging meals
Enable explicit date selection in detail view
Improve save interaction ergonomics
Problem

Current behavior:

- Meals copied from templates always get today's date
- Logging past days is cumbersome
- Detail view has no date control
- Save button requires scrolling

This breaks the expected mental model:

User context date ≠ system date (today)
Scope
In Scope
Date handling fix for meal creation
Date picker in detail view
Save button repositioning (detail + JSON view)
Out of Scope
Nutrition model changes
Meal structure changes
Historical analytics
Bulk editing
Expected Behavior
1. Date Context Preservation

When user is viewing a specific day:

All new meals must default to that selected date

Applies to:

- manual entry
- template copy
- JSON logging
2. Explicit Date Selection

In meal detail view:

User can override date via date picker

Behavior:

- default = current context date
- user can change date before saving
- date is persisted with the meal
3. Save Button UX

Update both:

- detail view
- JSON logging view

Change:

Save button is fixed in top-right corner
(always visible, no scrolling required)
Data Model

No schema changes expected.

Validate:

- meal.date field exists and is used consistently
Backend Changes

Ensure all create endpoints:

- accept date explicitly
- do NOT override with server "today"
- default date only if not provided

Critical rule:

Frontend date > server default
Frontend Changes
1. Context Date Propagation
Pass selected date into:
create meal flow
template copy flow
JSON logging
2. Detail View

Add:

Date picker component

Position:

Top section (near meal metadata)
3. Save Button

Apply to:

- detail editor
- JSON logging editor

Behavior:

- fixed position (top right)
- always visible
- triggers save
Design Principles
Respect user context over system defaults
Avoid hidden assumptions (like “today”)
Reduce friction for frequent actions
No unnecessary backend changes
Acceptance Criteria
Creating a meal respects selected date context
Template copy uses selected date, not today
JSON logging uses selected date
Detail view includes date picker
User can change meal date before saving
Save button is always visible (no scrolling required)
No regression in existing logging flows