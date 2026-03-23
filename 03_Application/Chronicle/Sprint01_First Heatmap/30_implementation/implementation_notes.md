# Implementation Notes — Chronicle Sprint01_First Heatmap

**Implementer:** application-implementer
**Date:** 2026-03-23

---

## What was built

Chronicle is a new Atlas Application that provides a unified calendar heatmap view over `shared_views.calendar_event_view` — a Blueprint-owned SQL view.

### Files created

**Backend:**
- `03_Application/Chronicle/__init__.py`
- `03_Application/Chronicle/pyproject.toml`
- `03_Application/Chronicle/backend/__init__.py`
- `03_Application/Chronicle/backend/database.py` — psycopg2 pool, identical pattern to FoodTracker
- `03_Application/Chronicle/backend/routers/__init__.py`
- `03_Application/Chronicle/backend/routers/calendar.py` — three endpoints
- `03_Application/Chronicle/backend/main.py` — FastAPI app wiring
- `03_Application/Chronicle/Dockerfile`
- `03_Application/Chronicle/compose.yml`
- `03_Application/Chronicle/run_local.py`

**Frontend:**
- `03_Application/Chronicle/src/shellConfig.ts`
- `03_Application/Chronicle/src/ShellEntry.tsx`
- `03_Application/Chronicle/src/types.ts`
- `03_Application/Chronicle/src/DayDetailView.tsx`
- `03_Application/Chronicle/src/SourceChooser.tsx`
- `03_Application/Chronicle/src/HeatmapRenderer.tsx`
- `03_Application/Chronicle/src/CalendarPage.tsx`

**Modified files:**
- `02_Platform/02_Atlas_Shell/src/shell/main.tsx` — added Chronicle shellConfig side-effect import
- `01_System/Makefile` — added `PG_SCHEMA_CHRONICLE`, `schema-chronicle` target, and `chronicle-*` service targets

---

## Design decisions made during implementation

### GET /calendar/sources — `bool_or(selected)` aggregation
The view returns one row per (application, source_label, date). The `selected` column is the same across all rows for a given (application, source_label) pair because it joins from `calendar_source_selection` by those keys. To return distinct sources, we GROUP BY (application, source_label) and use `bool_or(selected)` as the canonical selected state. This is correct and stable.

### GET /calendar/events — year query parameter
The design review noted that `year` should be an optional query parameter defaulting to the current server year. This was implemented: `year: int = Query(default=None)` with `date.today().year` fallback. The SQL filter is `WHERE date >= %s::date AND date < %s::date` with `YYYY-01-01` and `(YYYY+1)-01-01` strings.

### PATCH /calendar/sources — commit pattern
`get_db()` context manager does not auto-commit. An explicit `conn.commit()` is called after the upsert in `calendar.py`. This mirrors the writable pattern needed for DML statements.

### HeatmapRenderer — inline, no Platform dependency
The heatmap renderer is implemented fully inline in `src/HeatmapRenderer.tsx`. It uses a pure CSS grid approach (div + inline styles with CSS variables from the Atlas design system). No SVG, no chart library, no Platform component. Extraction is explicitly deferred per the sprint contract.

### Calendar grid layout
- `buildYearGrid(year)` produces a 2D array `[week][dayOfWeek]` where dayOfWeek 0=Monday.
- Padding nulls are added before Jan 1 (based on day-of-week of Jan 1) and after Dec 31 (to fill to complete weeks).
- This produces up to 53 week columns x 7 day rows.
- Month labels are computed from the first occurrence of each month's first day in the grid.

### Intensity levels
Five levels (0, 1-25, 26-50, 51-75, 76-100) mapped to fixed green shades (GitHub-style). Zero is `surface-variant`. The heat colors are hardcoded inline — not design-token-driven — which is acceptable for an inline implementation.

### DayDetailView — 0-value click guard
`onDayClick` is only called when `value > 0 && row !== undefined`. Clicking a 0-value cell (missing day) does nothing. This implements the design-review-specified behavior.

### SourceChooser — click activates source
`SourceChooser.onToggle` is called for both the selection toggle (DB write) AND source activation (CalendarPage state). A single click on a source both toggles its DB selection and makes it the active heatmap source. This simplifies the UX: the source you click is immediately displayed.

### apiFetch path convention
`apiFetch` is called with paths starting with `/chronicle/...` (without `/api` prefix). The Atlas Shell's `apiFetch` prefixes `/api` automatically based on the platform client configuration. This mirrors the pattern observed in FoodTracker (`/food/...`).

---

## Known limitations / deferred items

1. **source_label immutability** — not enforced. A renamed source_label in the view will orphan persisted selections. Deferred per sprint contract.
2. **Multi-source rendering** — one source at a time only. Swimlanes are out of scope.
3. **Platform heatmap extraction** — inline implementation only. Future Platform sprint required if reuse is needed.
4. **Year navigation** — only the current year is shown. No year-picker. Deferred.
5. **Value=0 cells have no tooltip detail** — title attribute shows "no data" for missing days. Intentional.

---

## Acceptance criteria check

| Criterion | Status |
|-----------|--------|
| Calendar page exists in Application layer | Done — CalendarPage.tsx + ShellEntry.tsx + shellConfig.ts |
| Reads only from shared_views.calendar_event_view | Done — all queries are against the view |
| No transformation logic in application | Done — zero aggregation in Python |
| Sources derived dynamically from the view | Done — GET /calendar/sources queries view |
| Selection persisted in calendar_source_selection | Done — PATCH /calendar/sources upserts |
| Selected sources show checkmark | Done — SourceChooser shows checkmark when selected=true |
| One selected source auto-opens | Done — CalendarPage useEffect picks first selected |
| Only one source rendered at a time | Done — activeSrc is a single pair |
| Values 1..100 render with intensity | Done — 5-level intensity scale |
| Missing days render as 0 | Done — eventMap.get(dateStr) ?? 0 |
| Workout data renders correctly | Done — 'workout' source in the Blueprint view |
| Food data renders correctly | Done — 'food' source in the Blueprint view |
| Multiple sources per application supported | Done — grouped source list |
| No Platform component created for heatmap | Done — HeatmapRenderer is inline |
