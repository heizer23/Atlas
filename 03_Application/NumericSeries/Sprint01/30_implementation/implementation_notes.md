# Implementation Notes — NumericSeries Sprint01

## Overview

Implemented the NumericSeries application from approved design artifacts
(`20_design/architecture.json`, `20_design/scaffolding.json`, `20_Data/schema.sql`).

---

## Backend

### What was pre-existing (from previous partial implementation session)
- `backend/database.py` — psycopg2 pool, init_schema, get_db context manager
- `backend/models.py` — all Pydantic request/response models
- `backend/service.py` — NumericSeriesService (sparkline, latest_value, list_series_rows, get_measurement_history, assemble_batch)
- `backend/label_client.py` — LabelClient and LabelClientError (httpx)
- `backend/routers/series.py` — all series and measurement CRUD endpoints

### Implemented this session
- `backend/main.py` — FastAPI app, CORS, platform middleware (install_exception_handlers, install_request_timing), router registration, startup hook calling init_pool() then init_schema()
- `backend/routers/batch.py` — POST /api/batch/series (batch read) and POST /api/series/{label_id}/values (external write)

### Open question resolution
The open question from design_review2.md — unknown label behavior for `POST /api/series/{label_id}/values` — was resolved as **404 SERIES_NOT_FOUND**. This is the conservative default: do not auto-create series on external write, and do not silently ignore the missing series. This matches the `SERIES_NOT_FOUND` failure mode declared in architecture.json.

### Dataset serialization
`_dataset_response()` helper added to series.py: wraps `Dataset` in `JSONResponse(content=ds.model_dump(by_alias=True, mode="json"))` to correctly serialize the `schema_` field as `"schema"` per the pydantic alias. Follows TaskTracker pattern.

### Port
Service runs on port 8014 as specified in architecture.json deferrals. Container name: `atlas-numeric-series`.

---

## Frontend

### Files created
- `src/ShellEntry.tsx` — shell outlet, nested Routes for /series (list) and /series/:label_id (detail)
- `src/shellConfig.ts` — AppRegistry.register with appId `numeric-series`, basePath `/series`
- `src/SeriesListPage.tsx` — custom list with recharts inline sparkline; parses sparkline_values JSON string
- `src/SeriesDetailPage.tsx` — measurement history table with add/edit/delete; delete series

### Sparkline
`react-sparklines` is not installed. Used recharts `LineChart` with height=28 and no axes/grid to render an inline sparkline. This satisfies the requirement to render sparkline_values as a visual chart without relying on unavailable dependencies.

### Shell registration
- Added `import '../../../../03_Application/NumericSeries/src/shellConfig'` to `02_Platform/Atlas_Shell/src/shell/main.tsx`
- Added `/api/series` and `/api/batch/series` proxy entries to `02_Platform/Atlas_Shell/vite.config.ts` targeting port 8014

---

## Design gaps encountered

None. All surfaces in architecture.json were implementable. The one flagged open question was resolved with the conservative default (404).

---

## Deferred items (not blocking this sprint)

- Tests (test_writer deferred per scaffolding.json)
- UI refinement (inline editing UX, sparkline axis configuration, empty state improvements)
- pyproject.toml created; no tests directory created this sprint
