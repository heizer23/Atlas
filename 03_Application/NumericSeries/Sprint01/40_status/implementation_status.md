# Implementation Status — NumericSeries Sprint01

## Overall Status: COMPLETE

All items in the sprint scope are implemented. The application is ready for human review.

---

## Backend checklist

| Item | Status | Notes |
|---|---|---|
| backend/main.py | DONE | FastAPI app, CORS, platform middleware, startup |
| backend/database.py | DONE (pre-existing) | Pool, schema init, get_db |
| backend/models.py | DONE (pre-existing) | All Pydantic models |
| backend/service.py | DONE (pre-existing) | Sparkline, latest_value, list, history, batch |
| backend/label_client.py | DONE (pre-existing) | LabelEngine HTTP client |
| backend/routers/series.py | DONE (pre-existing + fix) | CRUD + _dataset_response helper |
| backend/routers/batch.py | DONE | Batch read + external write |
| compose.yml | DONE | Port 8014, atlas-numeric-series |
| Dockerfile | DONE | Follows TaskTracker pattern |
| pyproject.toml | DONE | |
| schema.sql applied on startup | DONE | init_schema() called in startup hook |

## Frontend checklist

| Item | Status | Notes |
|---|---|---|
| src/shellConfig.ts | DONE | appId: numeric-series, basePath: /series |
| src/ShellEntry.tsx | DONE | Nested routes |
| src/SeriesListPage.tsx | DONE | Custom list with recharts sparkline |
| src/SeriesDetailPage.tsx | DONE | History table, add/edit/delete measurement, delete series |
| main.tsx registration | DONE | Side-effect import added |
| vite.config.ts proxy | DONE | /api/series → 8014, /api/batch/series → 8014 |

## Open question resolution

- POST /api/series/{label_id}/values with unknown label_id → **404 SERIES_NOT_FOUND** (conservative default)

## Architecture compliance

- sparkline_values encoded as JSON string (ColumnType: "string") per design — UI must parse
- SeriesListPage uses custom component, not standard TableView — per architecture constraint
- LabelEngine label is NOT deleted when a series is deleted
- Batch read includes unknown label_ids as empty series with label_name: null
- No domain logic in platform layer
- Sparkline derived at read time (not stored)

## Reviewer checklist (from architecture.json deferrals)

- [ ] Verify sparkline data is derived at read time and not stored
- [ ] Verify LabelEngine label is not deleted when a series is deleted
- [ ] Verify batch read includes unknown label_ids as empty series, not 404
- [ ] Verify external write endpoint validation matches API contract
- [ ] Verify no domain logic leaks into platform layer
- [ ] Verify compose.yml port (8014) does not conflict with existing services
