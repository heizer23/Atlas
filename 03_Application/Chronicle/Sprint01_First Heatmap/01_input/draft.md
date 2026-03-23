1. Slice name

Unified Calendar MVP: Shared View–Driven Heatmap

2. Goal

Deliver a minimal unified calendar application that renders daily heatmap data from a Blueprint-owned shared SQL view (CalendarEventView), with all transformation handled in the database and zero app-side aggregation.

3. User value

You get a single calendar page that:

shows daily activity/data from multiple applications
works immediately for workouts (first example)
can include new applications by only adding SQL to the shared view
remembers selected sources globally

This proves cross-application integration with minimal surface area.

4. Scope

Build a calendar page that:

reads from shared_views.calendar_event_view
lists all available (application, sourceLabel) combinations
allows selection (persisted globally)
renders one selected source at a time
displays a heatmap using values 0..100
treats missing days as 0

All logic is view-driven, not application-driven.

5. In scope / out of scope
In scope
Blueprint SQL view contract (chronicle.sql)
Global selection persistence via table
Unified Calendar page (Application layer)
Source chooser with checkmarks
One-source-at-a-time rendering
Heatmap visualization (inline implementation)
Workout + food examples supported via SQL
Out of scope
Platform-level reusable heatmap component
Multi-source rendering (swimlanes)
App-side aggregation or normalization
Units, value types, or schema polymorphism
Editing or creating events
Per-user preferences
Generic ingestion engine
6. Assumptions
Single user → selected is global
Database provides fully prepared rows
One row per (application, sourceLabel, date)
Values are already normalized to 1..100
Missing rows = empty day (0)
sourceLabel is stable within an application
AtlasShell already provides routing + layout
7. Open questions

None blocking.

Optional future clarifications:

enforce sourceLabel immutability
improve normalization logic for numeric sources
8. Required contracts
Blueprint ownership

CalendarEventView is defined as a shared SQL view:

Location:
00_Blueprint/SharedViews/chronicle.sql
Database schema:
shared_views
Applied via:
Makefile (Blueprint step)
Purpose
unify all calendar-ready data into one shape
allow apps to contribute via SQL only
keep application layer free of transformation logic
CalendarEventView contract (shared SQL view)
Required fields
date — canonical day
application — Atlas application identifier
sourceLabel — source identity + display label
label — day-level label
value — display-ready intensity (1..100)
selected — persisted global selection flag
Optional fields
detail
deep_link
Contract rules
identity = (application, sourceLabel)
rows are fully prepared in DB
no app-side aggregation
no app-side normalization
non-quantitative events use 100
missing day = no row → rendered as 0
selection is backed by a writable table and exposed via the view
9. Required components
Blueprint layer
Shared SQL View
shared_views.calendar_event_view
defined in chronicle.sql
Selection table
shared_views.calendar_source_selection
Application layer
Unified Calendar Page
entry point (/calendar)
Source Chooser
lists (application, sourceLabel)
shows checkmark for selected
Source Loader
filters by selected (application, sourceLabel)
Selection Persistence
updates calendar_source_selection
Day Detail View
shows date, application, sourceLabel, label, value
Heatmap Renderer (inline)
consumes values 0..100
implemented inside application
no reuse assumptions
Platform layer
AtlasShell
provides layout, routing, app hosting
calendar page is rendered inside it
No new Platform components introduced in this slice
10. Minimal user flow
User opens /calendar
App queries:
calendar_event_view
extracts distinct (application, sourceLabel, selected)
Chooser displays all sources
Selected sources show checkmark
App auto-opens one selected source
App loads rows filtered by that source
Heatmap renders:
value for existing days
0 for missing days
User clicks a day
Detail view shows:
date
application
sourceLabel
label
value
User toggles selection → persisted globally
11. Acceptance criteria
Calendar page exists in Application layer
Reads only from shared_views.calendar_event_view
No transformation logic exists in application
Sources are derived dynamically from the view
Selection is persisted in calendar_source_selection
Selected sources show checkmark
One selected source auto-opens
Only one source is rendered at a time
Values render correctly:
1..100 → intensity
missing → 0
Workout data renders correctly
Food data renders correctly
Multiple sources per application supported
No Platform component created for heatmap
12. Suggested implementation order
Finalize Blueprint SQL
ensure chronicle.sql runs cleanly
verify view returns correct rows

Seed initial selection

INSERT INTO shared_views.calendar_source_selection (application, source_label, selected)
VALUES ('workout', 'Workout Days', TRUE)
ON CONFLICT DO NOTHING;
Build Unified Calendar page
route + layout inside AtlasShell
Load sources
query distinct (application, sourceLabel, selected)
Implement chooser
list all sources
toggle selection

Implement selection update

INSERT INTO shared_views.calendar_source_selection (application, source_label, selected)
VALUES ($1, $2, $3)
ON CONFLICT (application, source_label)
DO UPDATE SET selected = EXCLUDED.selected;
Load selected source data
filter by (application, sourceLabel)
Render heatmap
inline component
map missing days → 0
Add day detail interaction
Out of scope (explicit)
reusable Platform heatmap component
multiple sources at once
swimlanes
normalization logic in app
schema generalization
cross-source comparisons