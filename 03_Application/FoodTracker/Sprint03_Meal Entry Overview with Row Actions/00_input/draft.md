Next Slice: Meal Entry Overview with Single-Entry Management
Purpose

Add a dedicated Entries screen so the user can see all logged meal entries and manage a single entry end to end: delete it, copy it, or open it in a detail view to modify it. This fills a current product gap: the app can create entries and report aggregates, but it does not yet expose any meal-level read or management surface.

Scope
Included
A new Entries screen in the FoodTracker app shell.
Read access to individual rows from foodtracker.food_logs.
A simple list of existing entries with enough summary data to identify each meal.
Three row actions on each entry:
delete
copy
open detail view
A detail view for one existing entry.
Editing of all meal fields already supported by the meal contract, except system-managed metadata.
Save flow that updates the existing row.
Copy flow that creates a new row and then opens that new row in detail view.
Hard delete behavior with explicit confirmation.
Excluded
Bulk actions.
Search, filtering, sorting controls, or pagination.
Inline editing in the list.
Undo, soft delete, or audit history.
Report drilldown into entries.
New nutrition fields or schema changes unless strictly required.
Autosave, drafts, or conflict resolution.
Authentication or authorization changes.
User Flow
User opens the Entries screen from FoodTracker navigation.
User sees all existing meal entries as a list.
From any row, the user can:
delete the entry
copy the entry
open the entry in detail view
If the user deletes, they must confirm before the row is permanently removed.
If the user copies, the system creates a new entry with the same meal content, sets logged_at to now, and navigates directly into that copied entry’s detail view.
If the user opens detail view, the system loads the current stored values for that entry.
User edits any supported meal fields except system-managed metadata and saves.
On success, the stored row is updated and the overview reflects the new values.
Principles
Keep the slice focused on single-entry management.
Reuse the existing meal validation and normalization rules for edit and copy-derived saves.
Prefer a clear end-to-end management loop over advanced browsing controls.
Keep destructive actions explicit and irreversible within this slice.
Do not introduce new domain concepts beyond “entry overview” and “entry detail.”
Data Contract
Overview list

A new read contract is required for meal-level rows. The current reporting dataset is aggregated and cannot support row-level actions, and the current commit dataset is only returned immediately after create.

Minimum overview row fields:

id
logged_at
meal_type
dish_name
kcal
Detail view

A new single-entry read contract is required to load one existing stored meal for editing. The payload should expose the full editable meal shape already supported by the current meal contract.

Editable fields:

logged_at
meal_type
meal content fields already supported by the existing meal contract
nutrition fields already supported by the existing meal contract
optional user-editable fields such as notes

Non-editable system-managed fields:

id
created_at
updated_at
Mutations

New mutation contracts are required for:

delete entry by id
update entry by id
copy entry by id

Copy behavior is defined for this slice as:

create a new entry with the same meal content
assign a new identity
set logged_at to the current time
navigate to the copied entry’s detail view
System Behavior
Entries screen
Displays one row per stored meal entry from foodtracker.food_logs.
Shows a clear empty state when no entries exist.
Shows an error state if load fails.
Each row exposes delete, copy, and open-detail actions.
Delete
Delete is a hard delete.
Delete requires explicit user confirmation before commit.
After success, the entry is removed from persistent storage and no longer appears in the overview.
Copy
Copy duplicates the selected entry into a new stored row.
The copied row receives a new id.
The copied row sets logged_at to current time.
After copy succeeds, the app navigates directly to the copied row’s detail view.
Detail view / modify
Opening detail view loads one existing row by id.
The edit flow reuses the same validation and normalization rules as the existing meal flow.
Saving updates the existing row rather than creating a second row.
After success, overview reflects the updated summary values.
Because updated_at currently has no update trigger, this slice should not assume automatic database maintenance of that field.
Architecture Impact
Adds a third user-facing domain beside intake and reporting: entry management.
Introduces the first meal-level read interface over foodtracker.food_logs. Existing read behavior is aggregate-only for reporting, while the create response is not a reusable browse interface.
Introduces the first update and delete capabilities, which are explicitly outside current scope today.
Requires an additional shell navigation item because current navigation exposes only Log and Report.
Constraints
Backend CORS currently allows GET POST only, so this slice must either express mutations within that constraint or deliberately expand platform configuration as part of the slice.
The existing table already contains the fields needed for overview and detail editing; avoid schema changes unless a true blocker appears.
Existing intake behavior validates and normalizes statelessly before write; edit behavior should reuse that same contract rather than introduce a second meal model.
User-local timezone handling is already out of scope, so “set logged_at to now” should follow the same current time baseline used elsewhere in the app.
Acceptance Criteria
User can navigate to an Entries screen from the FoodTracker app.
Entries screen lists existing rows from foodtracker.food_logs.
Each row shows enough summary information to identify the meal.
Each row has delete, copy, and open-detail actions.
Delete requires confirmation and performs a hard delete.
After delete succeeds, the row is gone from storage and from the refreshed list.
Copy creates a new row with the same meal content, a new identity, and logged_at set to current time.
After copy succeeds, the app opens the copied entry in detail view.
Detail view loads current stored values for a single entry.
User can edit all supported meal fields except id, created_at, and updated_at.
Save reuses the existing meal validation and normalization rules.
Save updates the original row and refreshed overview shows the updated summary values.
Empty and error states exist for the overview screen.
Open Questions

None blocking for this slice.

Out of Scope
Batch delete or batch copy.
Search, filtering, sorting preferences, or pagination.
Entry history or restore.
Edit from report charts.
Duplicate detection.
Export or sharing.
Test strategy changes unrelated to this slice’s behavior.