1. Slice Name

Chronicle Sprint02: Swimlanes and Selector

2. Goal

Extend Chronicle so that related sources from the same application group are
displayed together in the chooser as collapsible groups, and so that up to four
selected sources from a group can be rendered simultaneously as side-by-side
swimlanes in a single transposed calendar view.

Sprint01 established the foundation: Blueprint SQL view, single-source heatmap,
flat source chooser, day-detail view. This sprint evolves the presentation layer
without altering the underlying data contract principles.

3. User Value

The user can now:

- See sources organized by application group in the chooser, collapsed by default.
- Expand a group such as FoodTracker and check individual sources (e.g. Protein
  Intake, Calories).
- View up to four selected sources (from any application) as swimlanes in one
  transposed calendar — month progression vertical, weekdays horizontal.
- Tap a populated cell in any swimlane and get day detail for that exact source
  and date.

This improves overview, comparison, and mobile readability without changing the
data contract or introducing app-side aggregation.

4. Scope

4a. In Scope

- SourceChooser redesign: collapsible groups using the existing `application`
  field, individually selectable sources within a group, maximum four checked
  sources enforced in the chooser. Group order and source order follow the order
  returned by the SQL query — no additional sort column required.
- Multi-source rendering: CalendarPage routes selected sources to SwimlaneRenderer
  (new component); HeatmapRenderer is retired.
- Transposed grid layout: weekday headers run left-to-right, month progression
  runs top-to-bottom, month labels appear at the left margin aligned to the first
  row of each month.
- Selection model update: selection remains source-level and persisted globally
  in shared_views.calendar_source_selection. The chooser must clearly separate
  the expand/collapse gesture from the check/uncheck gesture.

4b. Out of Scope

- Group-level selection (checking an entire application group at once).
- More than four simultaneous checked sources.
- Arbitrary user-defined swimlane ordering.
- App-side aggregation or normalization.
- Year navigation.
- Platform extraction of the heatmap renderer.
- Source-label immutability enforcement.
- Generic dashboard or comparison mode.
- Per-user preferences.

5. Baseline State (Sprint01 Artifacts)

The following components exist and must be extended or replaced, not duplicated:

Backend:
  GET  /api/chronicle/calendar/sources  → list[SourceListRow]
  GET  /api/chronicle/calendar/events   → list[CalendarEventRow], filtered by
                                          (application, source_label, year)
  PATCH /api/chronicle/calendar/sources → upsert selection state

Frontend:
  CalendarPage.tsx   — orchestrates sources, active source, day detail
  SourceChooser.tsx  — flat list, single-click toggle+activate
  HeatmapRenderer.tsx — single source, [week][dayOfWeek] grid layout
  DayDetailView.tsx   — displays one CalendarEventRow
  types.ts            — SourceListRow, CalendarEventRow

Blueprint:
  shared_views.calendar_event_view     — (date, application, source_label,
                                         label, value, selected, detail,
                                         deep_link)
  shared_views.calendar_source_selection — primary key (application, source_label)

The current SourceListRow is:
  { application: string; source_label: string; selected: boolean }

The current CalendarEventRow is:
  { date, application, source_label, label, value, selected, detail, deep_link }

6. Required Data Contract Changes

6a. Blueprint SQL View (chronicle.sql)

No new columns required. The existing `application` field already provides
group identity. Source ordering is determined by the ORDER BY clause in the
SQL query; the application layer must not re-sort or derive order independently.

6b. GET /calendar/sources — no shape changes

The existing SourceListRow shape is sufficient:
  {
    application:  string
    source_label: string
    selected:     boolean
  }

The backend must return rows in a stable display order (SQL ORDER BY). No
additional fields are needed for grouping or sorting.

6c. Frontend Types (types.ts)

No changes to SourceListRow or CalendarEventRow. The chooser groups by the
existing `application` field.

6d. Multi-Source Events Fetch

The frontend will call GET /calendar/events once per selected source (same API,
called in parallel for up to four sources). No batch endpoint is needed in this
sprint.

7. Component Responsibilities

7a. Blueprint (chronicle.sql)

- No changes required. The existing `application` column provides group identity
  and the SQL ORDER BY controls source ordering within each group.
- Future source additions define their own order via the query; no schema change
  is needed.

7b. GET /calendar/sources (calendar.py)

- No field changes. Ensure the query returns rows in a stable display order
  (ORDER BY application, source_label or as defined in the SQL view) so the
  frontend can render groups without re-sorting.

7c. SourceChooser (SourceChooser.tsx — full replacement)

Input props:
  sources:          SourceListRow[]          — flat list in SQL-defined order
  onToggle:         (application, source_label, selected: boolean) => void
  selectedCount:    number                   — total currently selected sources
  maxSelected:      number                   — hard cap (4)

Behavior:
  - Group sources by the existing `application` field, preserving the order
    returned by the backend (SQL-defined; no client-side re-sorting).
  - Render one collapsible section per group; groups collapsed by default.
  - Expand/collapse is a local UI gesture (no persistence, no API call).
  - Each source row inside a group shows a checkbox-style indicator for selected
    state.
  - Clicking a source row calls onToggle with !selected.
  - If selectedCount >= maxSelected and the source is not currently selected,
    clicking is blocked (the row is visually disabled).
  - No single-click activate behavior. Activation is determined by selected state
    only (see CalendarPage).

7d. CalendarPage (CalendarPage.tsx — significant changes)

- Remove single activeSrc state; replace with selectedSources: SourceListRow[]
  derived from sources.filter(s => s.selected).
- Pass selectedCount and maxSelected to SourceChooser.
- When selectedSources changes, render the swimlane view.
- Pass selectedSources to SwimlanRenderer (new component, see 7e).
- Retain DayDetailView for day-click handling.
- Retain loading, error, and empty-state behavior.
- Empty state: no sources selected → show chooser with prompt text.

7e. SwimlaneRenderer (new component — SwimlaneRenderer.tsx)

Replaces the direct HeatmapRenderer usage for multi-source rendering.

Input props:
  sources:       SourceListRow[]                       — 1..4 selected sources
  onDayClick:    (row: CalendarEventRow) => void

Behavior:
  - Fetches events for each source in parallel (one GET /calendar/events call per
    source).
  - Builds one eventMap per source.
  - Renders a single transposed year grid shared by all swimlanes:
      - Rows = weeks (one row per week, ~52 rows).
      - Columns = days of week (Mon..Sun, 7 columns).
      - Month labels on the left margin at the first row of each month.
  - For each week row, renders one sub-row per source (the swimlane).
  - Each cell within a swimlane sub-row maps to one (source, date) pair.
  - Intensity logic per cell is unchanged: 0/1-25/26-50/51-75/76-100 → heat-0
    through heat-4.
  - Missing days render as heat-0, non-interactive.
  - Populated days are clickable → onDayClick with the CalendarEventRow for
    that source and date.
  - Swimlane label (source_label) appears at the left of each swimlane sub-row
    within the week block, or as a header row above the first week.
  - Loading state: show Skeleton until all source fetches complete.
  - Error state: if any source fetch fails, surface ErrorCard for that source;
    continue rendering successful sources.
  - Inline implementation — no Platform dependency.

7f. HeatmapRenderer (retired)

HeatmapRenderer.tsx is removed. SwimlaneRenderer fully subsumes its
responsibility. CalendarPage must no longer reference it.

7g. DayDetailView (existing — no changes required)

The DayDetailView contract is unchanged. It receives one CalendarEventRow and
displays it. SwimlaneRenderer passes the correct row on cell click.

8. Interaction Rules (Preserved from Sprint01)

- Missing or zero-value cells are non-interactive (no DayDetailView shown).
- Populated cells (value > 0) open DayDetailView for the exact source and date.
- Source selection is persisted globally via the existing PATCH endpoint.
- The selected flag in SourceListRow reflects persisted state from the backend.

9. Transposed Grid Layout Specification

Current Sprint01 layout (HeatmapRenderer):
  - Columns: weeks (left to right, ~52 columns)
  - Rows: days of week (top to bottom, Mon-Sun, 7 rows)
  - Month labels: above columns

New transposed layout (SwimlaneRenderer):
  - Rows: weeks (top to bottom, ~52 rows)
  - Columns: days of week (left to right, Mon-Sun, 7 columns)
  - Month labels: left margin, at the first row where each month appears
  - For multi-source: each week row expands into N sub-rows (one per source),
    with source label at the left margin of the first sub-row in each week block.

The cell size, gap, intensity color scale, and border-on-hover behavior from
Sprint01 are preserved.

10. Assumptions

- Single user — selection is still global.
- Database provides fully prepared rows; no app-side aggregation.
- One row per (application, source_label, date) in the view.
- Values are already normalized to 1..100 in SQL.
- Source grouping identity comes from the existing `application` field.
- Source ordering is defined by the SQL query; the frontend does not re-sort.
- AtlasShell routing and layout are unchanged.
- Shell Dockerfile COPY, nginx.conf, vite.config.ts, and Makefile are all
  already wired from Sprint01. No new deployment wiring needed.

11. Open Questions

None blocking.

The following are deferred and do not need designer resolution:
  - Exact pixel dimensions for swimlane sub-rows and swimlane labels.
  - Color differentiation between swimlanes (same scale per lane is acceptable
    as a first cut).

12. Acceptance Criteria

- The chooser displays collapsible groups; groups are collapsed by default.
- Expanding a group reveals individual source entries.
- Source selection is individual; no group-level checkbox exists.
- No more than four sources can be selected simultaneously; the chooser enforces
  this by disabling unchecked sources when the limit is reached.
- Selected sources from the same group render together as swimlanes.
- Swimlane order follows the order returned by GET /calendar/sources (SQL-defined).
- The calendar grid is transposed: weekdays are horizontal, month progression is
  vertical.
- Month labels appear at the left margin of the first row for each month.
- Intensity behavior per cell is unchanged (five levels, heat-0 through heat-4).
- Missing or zero-value cells are non-interactive.
- Clicking a populated cell opens DayDetailView for that exact source and date.
- No aggregation or normalization logic is introduced in the application layer.
- The existing `application` field is the sole source of group identity.
- HeatmapRenderer is removed; SwimlaneRenderer handles all rendering.
- All existing loading, error, and empty-state behaviors are preserved.
- The application continues to read only from Blueprint-owned views and the
  selection table.

13. Suggested Implementation Order

1. Verify GET /calendar/sources returns rows in stable SQL-defined order
   (no backend changes expected; confirm ORDER BY is in place).
2. Implement SwimlaneRenderer with transposed grid and multi-source swimlane
   logic.
3. Rewrite SourceChooser: grouped by `application`, collapsible, max-four
   enforcement.
4. Update CalendarPage: multi-select state model, route to SwimlaneRenderer,
   remove HeatmapRenderer reference.
5. Delete HeatmapRenderer.tsx.
6. Smoke-test: expand a group, select two sources, verify swimlane render and
   day-detail.
7. Verify max-four enforcement: attempt to check a fifth source — must be
   blocked by chooser.
