# Sprint02 — NumericSeries — Chronos Write Endpoint + UX Polish

## Context

NumericSeries is an existing application at `03_Application/NumericSeries`.
Backend: FastAPI/Python. Frontend: React/TypeScript (custom list + detail views).
Sprint01 is complete. This sprint makes targeted UX and API changes.

---

## Changes

### 1 — Remove inline create form; replace with "+" button

**Current:** `SeriesListPage` renders a `CreateForm` above the series list.

**New:** Remove the `CreateForm` entirely. Replace with a small `+` button (top-right of the page header). Clicking it navigates to `/series/new`.

The `/series/new` route already matches the existing `:label_id` route — `SeriesDetailPage` must detect `label_id === 'new'` and render a creation form instead of the measurement view.

**Creation mode in SeriesDetailPage:**
- Shows a single text input: "Series name"
- Submit button: "Create"
- On success: `POST /api/series` → redirect to `/series/:label_id` using the returned `label_id`
- On error: show inline error
- Back button: navigates to `/series`
- No measurements table, no delete button in creation mode

### 2 — Fix list row styling

**Current:** Rows use hardcoded dark colors (`background: #1e1e2e`, `border: 1px solid #2e2e3e`). The label name is invisible against the dark background.

**New:** Use CSS theme tokens matching the rest of the app (same pattern as FoodTracker):
- `background: var(--md-sys-color-surface)`
- `border: 1px solid var(--md-sys-color-outline-variant)`
- `border-radius: var(--radius-card)` (or `8px`)
- Label name: `color: var(--md-sys-color-on-surface)`, `fontWeight: 500`
- Latest value: `color: var(--md-sys-color-on-surface-variant)`
- Sparkline stroke: keep `#7c6af5` (intentional accent)
- Empty sparkline "—": `color: var(--md-sys-color-on-surface-variant)`

No other structural changes to the list.

### 3 — Chronos write-by-name endpoint

**New backend endpoint:** `POST /api/series/by-name/{label_name}/values`

Allows Chronos to append a measurement using the human-readable series name, without needing to look up the label_id first.

**Request body** (same shape as existing `/values` endpoint):
```json
{ "entries": [{ "value": 72.3, "recorded_at": "2026-04-12T08:00:00Z" }] }
```

**Behavior:**
- Look up `label_name` in `numeric_series.series` (join on `labels.labels`)
- If not found: `404 SERIES_NOT_FOUND`
- If found: insert measurements, return `{"inserted": N}`
- Name matching: case-insensitive, exact match

**Implementation location:** `backend/routers/batch.py` (alongside the existing external write endpoint).

Uses `ExternalWriteRequest` model (already exists).

---

## Out of scope

- No changes to measurement edit/delete UI
- No changes to the batch read endpoint
- No schema changes
- No new sprint artifacts needed beyond this draft (direct implementation)
