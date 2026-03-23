# Chronicle – Implementation Status

## 1. Purpose

Chronicle renders a unified calendar heatmap for the current year, sourced from the Blueprint-owned shared SQL view `shared_views.calendar_event_view`. It allows the user to browse available data sources, toggle global selection per source, and inspect day-level detail for any active source.

## 2. Current Concept

The application is built around a view-driven architecture: all data transformation, aggregation, and normalization is performed by the Blueprint SQL view. The application layer performs no computation on the data it receives. A global source-selection table (`shared_views.calendar_source_selection`) persists which sources the user has chosen. The frontend renders a 52-column × 7-row year grid from sparse row data, treating missing dates as value 0.

## 3. Current Capabilities

- Fetches all distinct (application, source_label, selected) pairs from `calendar_event_view` and displays them in a source chooser panel with a checkmark indicator for selected sources.
- Persists source selection globally by upserting into `shared_views.calendar_source_selection` via a PATCH endpoint; persistence is confirmed by server response, not optimistic-only.
- Auto-opens the first selected source on page load.
- Activates a source for heatmap viewing when its row is clicked in the chooser (regardless of toggle state).
- Renders a full-year heatmap grid (current calendar year, Mon–Sun rows, week columns) for the active source using five intensity levels: no-data, 1–25, 26–50, 51–75, 76–100.
- Treats days absent from the event response as value 0 (lightest shade, no interaction).
- Shows day-level detail (date, application, source_label, label, value, optional detail and deep_link) on clicking any cell with value > 0.
- Suppresses day-detail interaction for 0-value / missing-day cells.
- Surfaces loading state via Skeleton and error state via ErrorCard on both the sources load and events load.
- Provides an empty-source prompt message when no source is active (no auto-open on first use with no selection).
- Filters event data to the current calendar year using a server-side SQL date range filter; year is passed as a query parameter from the client.
- Validates the year parameter server-side (rejects values outside 2000–2100).

## 4. Current Data Model

Chronicle has no private application tables. It reads from one Blueprint-owned view and writes to one Blueprint-owned table.

**Blueprint-owned (referenced, not owned by Chronicle):**

| Name | Key Fields | Purpose |
|---|---|---|
| `shared_views.calendar_event_view` | (application, source_label, date) | Blueprint SQL view unifying workout and food calendar data with selection state |
| `shared_views.calendar_source_selection` | (application, source_label) — primary key | Writable table persisting global source selection |

These are defined in `00_Blueprint/SharedViews/chronicle.sql` and are not owned by the application layer.

## 5. Contracts Consumed

- **CalendarEventViewRow** (v1.0) — Blueprint-owned. Fields: date, application, source_label, label, value (1..100), selected, detail (optional), deep_link (optional). Identity: (application, source_label, date). Defined in `Sprint01_First Heatmap/20_design/architecture.json`.
- **SourceListRow** (v1.0) — Derived from CalendarEventViewRow. Fields: application, source_label, selected. Defined in `Sprint01_First Heatmap/20_design/architecture.json`.
- **SelectionToggleRequest / SelectionToggleResponse** (v1.0) — Request and response body for PATCH /api/chronicle/calendar/sources. Defined in `Sprint01_First Heatmap/20_design/architecture.json`.
- **AtlasShell AppRegistry** — shell registration contract; Chronicle registers via `shellConfig.ts` side-effect import.
- **@platform-ui/api/client** — `apiFetch`, `isApiError`.
- **@platform-ui/components/ErrorCard**, **@platform-ui/components/Skeleton** — UI primitives.
- **platform_errorhandling** — `setup_logging`, `install_exception_handlers`, `install_request_timing`.

## 6. Interfaces Exposed

### 6.1 API Endpoints

**GET /api/chronicle/calendar/sources**
- Purpose: Returns all distinct data sources available in calendar_event_view with their current selection state.
- Input: None.
- Output: `list[SourceListRow]` — JSON array of `{ application, source_label, selected }`.

**GET /api/chronicle/calendar/events**
- Purpose: Returns all CalendarEventViewRow entries for a given source and year. Missing days are not included; frontend renders them as 0.
- Input: Query params — `application` (string, required), `source_label` (string, required), `year` (integer, optional, defaults to current server year, validated 2000–2100).
- Output: `list[CalendarEventViewRow]` — JSON array of `{ date, application, source_label, label, value, selected, detail, deep_link }`.

**PATCH /api/chronicle/calendar/sources**
- Purpose: Upserts the selection state of an (application, source_label) pair in `calendar_source_selection`.
- Input: `SelectionToggleRequest` body — `{ application, source_label, selected }`.
- Output: `SelectionToggleResponse` — `{ application, source_label, selected }` reflecting the persisted state, or ApiError.

### 6.2 UI Datasets

No Dataset-shaped UI data contracts are used. The heatmap endpoints use the CalendarEventViewRow named contract, which is a controlled deviation from the default Dataset contract. The non-Dataset justification is declared in `architecture.json` (heatmap requires date-sparse access; Dataset pagination semantics do not apply).

### 6.3 Events Emitted

None identified.

### 6.4 Events Consumed

None identified.

### 6.5 External / Platform Dependencies

- **AtlasShell** (`02_Platform/02_Atlas_Shell`) — routing, layout, app hosting. Chronicle is registered via side-effect import in `02_Platform/02_Atlas_Shell/src/shell/main.tsx`.
- **platform_errorhandling** (`02_Platform/packages/platform_errorhandling`) — logging, exception handlers, request timing middleware.
- **@platform-ui** (`02_Platform/UI/react/src`) — ErrorCard, Skeleton, apiFetch, isApiError, ApiError type.
- **PostgreSQL** — accessed via psycopg2 SimpleConnectionPool; ATLAS_PG_* environment variables; shared_views schema.

## 7. Known Gaps

### 7.1 Implementation Gaps

- **Year navigation**: Only the current calendar year is displayed. No year-picker or navigation to prior/future years. The GET /calendar/events endpoint supports a `year` query parameter, but the frontend always passes the current year. Noted as a deferred item by the implementer.
- **source_label immutability not enforced**: A source_label renamed in the Blueprint view will silently orphan the persisted selection row in `calendar_source_selection`. This is a known assumption in the design (MVP deferral) and logged in architecture.json invariants, but no enforcement or detection mechanism exists.

### 7.2 Inconsistencies

- **architecture.json lists `platform_contracts` as a backend platform dependency** (for Dataset, DatasetMeta, ColumnSchema), but `calendar.py` does not import from `platform_contracts` at all and `pyproject.toml` does not list it as a dependency. The architecture note qualifies this as "imported for consistency but CalendarEventView endpoints use named contracts, not Dataset." The implementation correctly omits the import per the design review instruction. The architecture.json description is misleading but not a functional error.

### 7.3 Conformance Issues

- **`architecture.json` `backend.platform_dependencies` states `platform_contracts` is consumed** — the implementation does not import or depend on `platform_contracts`. This is a documentation mismatch in the design artifact, not an implementation defect. The design review explicitly instructed the implementer not to import Dataset if unused. The implementation is correct; the artifact description is inaccurate.

### 7.4 Missing or Ambiguous Design Baseline

None identified. All design artifacts are present, approved, and concrete. The design review is approved with no blocking issues. The implementation follows the scaffolding and architecture definitions.

## 8. Non-Scope

- Platform-level reusable heatmap component — explicitly deferred; HeatmapRenderer is inline and application-private.
- Multi-source rendering or swimlane views — one source displayed at a time.
- App-side data aggregation or normalization — all transformation is in the Blueprint SQL view.
- Per-user preferences — selection is global (single-user assumption).
- Editing or creating calendar events — Chronicle is read-only except for source selection toggle.
- Year navigation — only the current year is accessible in this sprint.
- Generic ingestion engine or schema polymorphism — sources are defined as SQL in the Blueprint view.
- Deep-link navigation (the `deep_link` field is displayed in DayDetailView when present, but Chronicle itself does not route to source applications).

## 9. Recommendation

### Recommended Owner

None

### Reason

The implementation is complete, correct, and consistent with all explicit design artifacts. All acceptance criteria are met. The two deferred items (year navigation, source_label immutability enforcement) are documented and acknowledged. The platform_contracts documentation mismatch in architecture.json is a minor inaccuracy in the design artifact and does not affect runtime behavior.

### Suggested Next Action

No action required for Sprint01. If year navigation or multi-year support is needed, that belongs in a subsequent sprint definition.

### Priority

Low

---

## Validation Warnings

- **architecture.json `backend.platform_dependencies` describes `platform_contracts` as consumed** — this is inaccurate. The implementation does not import platform_contracts, and the design review explicitly instructed the implementer not to. The artifact description should be corrected to remove this misleading entry, but it has no runtime impact.
