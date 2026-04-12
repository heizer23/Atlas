# Test Spec — NumericSeries — Sprint02_ChronosAndUX

## Scope

Tests cover the new `POST /api/series/by-name/{label_name}/values` endpoint. Frontend UX changes (creation mode, row styling) are excluded from automated test scope this sprint.

## Scenarios

### Happy path — single entry inserted by name

- **Given:** A series exists for label name "Weight" (fixture: label id `fix-label-weight`, series record present)
- **When:** `POST /api/series/by-name/Weight/values` with body `{"entries": [{"value": 72.3, "recorded_at": "2026-04-12T08:00:00Z"}]}`
- **Then:** Response is 200 with body `{"inserted": 1}` and a measurement row exists in the database for label_id `fix-label-weight` with value 72.3

### Happy path — multiple entries inserted

- **Given:** A series exists for label name "Weight"
- **When:** `POST /api/series/by-name/Weight/values` with `{"entries": [{"value": 70.0, "recorded_at": "2026-04-10T08:00:00Z"}, {"value": 71.5, "recorded_at": "2026-04-11T08:00:00Z"}]}`
- **Then:** Response is 200 with body `{"inserted": 2}` and two measurement rows are inserted

### Case-insensitive name match

- **Given:** A series exists for label name "Weight"
- **When:** `POST /api/series/by-name/weight/values` (lowercase)
- **Then:** Response is 200 with `{"inserted": 1}` — name match is case-insensitive

### Series not found — label exists but no series record

- **Given:** A label exists with name "Daily Steps" (fixture: `fix-label-steps`) but no corresponding series record in `numeric_series.series`
- **When:** `POST /api/series/by-name/Daily%20Steps/values` with a valid entry
- **Then:** Response is 404 with error code `SERIES_NOT_FOUND`

### Series not found — label does not exist at all

- **Given:** No label named "Nonexistent" exists
- **When:** `POST /api/series/by-name/Nonexistent/values` with a valid entry
- **Then:** Response is 404 with error code `SERIES_NOT_FOUND`

### Invalid value — non-finite number rejected

- **Given:** A series exists for label name "Weight"
- **When:** `POST /api/series/by-name/Weight/values` with `{"entries": [{"value": null, "recorded_at": "2026-04-12T08:00:00Z"}]}`
- **Then:** Response is 422 with error code `INVALID_VALUE` (or Pydantic validation error)

### Invalid timestamp rejected

- **Given:** A series exists for label name "Weight"
- **When:** `POST /api/series/by-name/Weight/values` with `{"entries": [{"value": 72.0, "recorded_at": "not-a-date"}]}`
- **Then:** Response is 422 with error code `INVALID_TIMESTAMP`
