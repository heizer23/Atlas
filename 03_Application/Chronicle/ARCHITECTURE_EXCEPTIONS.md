# Chronicle — Architecture Exceptions

This file registers approved deviations from Blueprint-level rules for the Chronicle application.
Governed by R-CON-BP-05 §3 (APPLICATION-scope exceptions are local and not centrally registered).

---

## EXC-CH-01 — Calendar endpoints use CalendarEventViewRow named contract, not Dataset

**RULE_ID:** EXC-CH-01
**EXCEPTION_TO:** R-CON-BP-04 (UI Data Contract)
**SCOPE:** APPLICATION (Chronicle)
**STATUS:** ACTIVE
**ENDPOINTS:**
- `GET /api/chronicle/calendar/sources` — returns a plain list of source records
- `GET /api/chronicle/calendar/events` — returns a plain list of calendar event rows
- `PATCH /api/chronicle/calendar/sources` — returns a single selection record

**Deviation:** These endpoints return custom list/object shapes rather than `Dataset`. No `meta`, `schema`, or paginated `rows` wrapper is used.

**Rationale:** The Chronicle calendar view is a heatmap/swimlane calendar that renders a full year of daily event data. This data is consumed by a custom calendar rendering component, not by a TableView or paginated list. The Dataset pagination model (`page`, `page_size`, `total`) has no semantic meaning for a year-at-a-glance calendar view. The event payload shape is driven by the `shared_views.calendar_event_view` SQL contract (`00_Blueprint/SharedViews/chronicle.sql`), which is itself a stable shared contract.

R-CON-BP-04 permits non-Dataset shapes when "Dataset is not a natural fit" and the alternate shape is defined as an explicit stable contract. The heatmap/event semantics satisfy this criterion.

**Named contracts** (declared in Sprint02 `20_design/architecture.json`):

- `CalendarSourceRow`: `{ application: string, source_label: string, selected: boolean }`
- `CalendarEventViewRow`: `{ date: string (YYYY-MM-DD), application: string, source_label: string, label: string, value: integer, selected: boolean, detail: string|null, deep_link: string|null }`
- `SourceSelectionResult`: `{ application: string, source_label: string, selected: boolean }`

**Stable shared view contract:** `00_Blueprint/SharedViews/chronicle.sql` defines the `shared_views.calendar_event_view` view that backs the event and source endpoints. Changes to the view schema are a breaking change to this contract.
