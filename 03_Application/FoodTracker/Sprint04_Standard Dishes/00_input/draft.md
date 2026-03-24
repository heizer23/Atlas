Purpose

Add a reusable Standards flow so a user can quickly log frequently used dishes such as “skyr breakfast” from a dedicated page, while defining or removing standard status from the existing Entries page. This slice also includes the required schema migration for standard, source_standard_id, and alcohol_g. It continues to build on the existing foodtracker.food_logs model and existing row-level entry operations already in place.

Scope
Included
Database migration on foodtracker.food_logs adding:
standard
source_standard_id
alcohol_g
Add three-dots row menu on Entries page with:
Standard / Remove Standard
Delete
Allow toggling standard status on any existing logged entry.
Add Standards as a main navigation item.
Add a Standards page with two sections:
top: today’s logged entries created from standards
bottom: all available standard dishes grouped by meal_type
Allow adding a new logged instance from a selected standard dish.
Allow deleting one logged instance from the top section.
Aggregate repeated same-day standard-derived entries in the top section and show count.
Nutritional totals in the top section reflect the sum across instances.
Excluded
Any UI or behavior using alcohol_g in this iteration.
Any repeated-instance behavior for non-standard dishes.
Quantity editing beyond creating or deleting one row at a time.
Editing the contents of a standard from the Standards page.
Separate standards entity/table.
Bulk actions.
Reporting changes.
User Flow
User opens Entries.
User opens the three-dots menu for an entry.
User selects Standard.
The entry becomes a reusable standard dish.
User opens Standards from main navigation.
Top section shows today’s logged entries that were created from standards, aggregated by dish.
Bottom section shows all standard dishes grouped by meal_type.
User selects a standard dish from the bottom section.
System creates a new food_logs row for now, copying the standard’s stored values and setting source_standard_id.
Top section updates, increasing the count for that dish and updating summed nutrition values.
User can:
add one more copy from the top section
delete one instance from the top section
If deleting from an aggregated row, the system deletes the most recently logged matching instance for today.
Principles
Reuse the existing food_logs table.
Treat a standard as a flag on an existing logged entry.
Track standard-derived copies explicitly with source_standard_id.
Keep persistence row-based; aggregation is UI-level only.
Do not solve generic quantity management in this slice.
Include alcohol_g in the migration only; do not expand scope to use it.
Data Contract
Database

Extend foodtracker.food_logs with:

standard BOOLEAN NOT NULL DEFAULT FALSE
source_standard_id UUID NULL
alcohol_g NUMERIC NOT NULL DEFAULT 0
Field semantics
standard
marks an entry as reusable in the Standards page
source_standard_id
references the standard entry a logged copy was created from
null for rows not created from a standard
alcohol_g
reserved for later use
persisted on rows now but not surfaced in UI/logic in this slice
Required backend capabilities
Toggle standard status
input: entry id, desired standard state
effect: updates the row
Fetch Standards page
available standards: rows where standard = true
today section: rows for current day where source_standard_id IS NOT NULL
Create logged copy from standard
input: standard id
effect:
creates a new row by copying relevant stored values
sets source_standard_id = selected_standard_id
sets standard = false on the new logged copy unless there is a deliberate need to preserve it as reusable
Delete one logged standard-derived instance
input: grouped dish context or specific row id
effect: deletes the most recently logged matching instance for today
Decided Behavior
Entries page
Row actions move under a three-dots menu.
Menu items:
Standard when standard = false
Remove Standard when standard = true
Delete
Toggling standard affects only the selected row.
Standards page
Top section: Today
Shows today’s rows created from standards.
Aggregated by standard-derived dish.
Each aggregated row shows:
dish name
count, e.g. × 2
summed nutrition values
Actions:
Add copy
Delete one
Bottom section: Standards
Shows all rows where standard = true
Grouped by meal_type
Selecting a row creates one new logged copy for today
Delete rule

When a grouped row has multiple instances, Delete one removes the most recently logged matching instance for today.

Navigation
Standards is a main nav item.
System Behavior
Standard definitions live as normal rows in food_logs.
Logging from a standard creates a separate new row.
The new row keeps copied nutrition values from the selected standard at the time of logging.
The top section only includes rows with source_standard_id set.
Non-standard rows do not get repeated-instance controls.
alcohol_g is stored but not shown or used in calculations specific to this slice unless it is already part of generic nutrition persistence behavior.
Architecture Impact
Backend
One migration covering:
standard
source_standard_id
alcohol_g
Entry read models must expose standard where needed.
Standards page requires read support for:
all standards
today’s standard-derived rows
Standard-copy creation must set source_standard_id.
Delete-one behavior must select the latest matching row for today.
Frontend
Entries row actions updated to three-dots pattern.
New Standards main nav route/page.
Standards page needs:
grouped standards list by meal_type
aggregated today list by source standard/dish
add-copy and delete-one actions
Existing implementation dependency

This slice extends the current entries-based workflow and existing entry row operations rather than introducing a separate subsystem.

Constraints
Must continue to use foodtracker.food_logs as the source model.
Must not introduce non-standard instance counting.
Must not expand this iteration into alcohol-related UX.
Must keep aggregation as display logic, not stored counters.
Must preserve the ability to distinguish reusable standards from standard-derived logged copies.
Acceptance Criteria
foodtracker.food_logs includes standard, source_standard_id, and alcohol_g.
Existing rows migrate successfully with safe defaults.
A user can mark and unmark an entry as standard from the Entries page.
Entries row actions are accessible via a three-dots menu.
Standards appears as a main navigation item.
The Standards page lists all standard dishes grouped by meal_type.
Selecting a standard creates a new logged row for the current day.
New rows created from standards store source_standard_id.
The top section shows today’s standard-derived logged entries only.
Repeated same-day logs from the same standard are shown as one aggregated row with the correct count.
Aggregated nutrition values equal the sum of the underlying rows.
Add copy creates one additional logged row from that standard.
Delete one removes the most recently logged matching instance for today.
Non-standard dishes do not show instance-increase behavior.
alcohol_g exists in the schema but does not introduce new UI in this slice.
Open Questions

None blocking for this slice.

Out of Scope
Using alcohol_g in forms, calculations, filters, or reports
Standard editing/versioning
Generic quantity multipliers
Repeated-instance controls for non-standard dishes
Bulk standard management
Historical backfill of source_standard_id
Report/UI changes outside Entries and Standards