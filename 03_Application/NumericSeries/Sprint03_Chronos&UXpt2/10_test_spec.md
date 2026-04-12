# Test Spec — NumericSeries — Sprint03_Chronos&UXpt2

## Scope
Tests cover the new GET /api/measurement-definitions endpoint, the new POST /api/measurements/batch endpoint (including atomicity and all error cases), and the sparkline_points field added to the list endpoint. Chronos skill mapping logic is tested as a unit (no live API call). UI behavior (input styling, timestamp formatting, datetime split input) is not covered by automated API tests.

## Scenarios

### Catalog endpoint returns all definitions
- **Given:** The measurement_definitions.json catalog is loaded at startup with at least the standard entries (weight, body_fat_pct, steps, etc.)
- **When:** GET /api/measurement-definitions is called
- **Then:** Response is a Dataset with object_type=measurement_definition; rows contain at least one entry; each row has id, key, label, unit, value_type, description fields; rows are ordered by label ASC

### Batch single measurement inserted
- **Given:** A series with label_name='weight' exists in the test fixtures
- **When:** POST /api/measurements/batch with body {recorded_at: '2026-04-12T08:00:00Z', measurements: [{key: 'weight', value: 80.5}]}
- **Then:** Response is 201 {inserted: 1}; one row exists in numeric_series.measurements for the weight series

### Batch multiple measurements inserted atomically
- **Given:** A series with label_name='weight' exists; a series with label_name='body_fat_pct' exists in fixtures
- **When:** POST /api/measurements/batch with body {recorded_at: '2026-04-12T08:00:00Z', measurements: [{key: 'weight', value: 80.5}, {key: 'body_fat_pct', value: 18.4}]}
- **Then:** Response is 201 {inserted: 2}; both measurements are in the database with the same recorded_at

### Batch rejects unknown key
- **Given:** The catalog does not contain a key 'unknown_metric'
- **When:** POST /api/measurements/batch with body {recorded_at: '2026-04-12T08:00:00Z', measurements: [{key: 'unknown_metric', value: 1.0}]}
- **Then:** Response is 422 ApiError with code UNKNOWN_KEY; no rows inserted

### Batch rejects missing recorded_at
- **Given:** Any valid series exists
- **When:** POST /api/measurements/batch with body {measurements: [{key: 'weight', value: 80.5}]} (no recorded_at field)
- **Then:** Response is 422 validation error; no rows inserted

### Batch rejects invalid value
- **Given:** A series with label_name='weight' exists
- **When:** POST /api/measurements/batch with body {recorded_at: '2026-04-12T08:00:00Z', measurements: [{key: 'weight', value: null}]} or a non-finite float
- **Then:** Response is 422 ApiError with code INVALID_VALUE; no rows inserted

### Batch atomicity — first valid second invalid
- **Given:** A series with label_name='weight' exists; no series for 'unknown_metric'
- **When:** POST /api/measurements/batch with body {recorded_at: '2026-04-12T08:00:00Z', measurements: [{key: 'weight', value: 80.5}, {key: 'unknown_metric', value: 1.0}]}
- **Then:** Response is 422 UNKNOWN_KEY; the weight measurement is NOT inserted (atomicity: all-or-nothing)

### Batch rejects series not found for valid catalog key
- **Given:** 'steps' is a valid catalog key; no series row exists for the 'steps' label in the test fixtures
- **When:** POST /api/measurements/batch with body {recorded_at: '2026-04-12T08:00:00Z', measurements: [{key: 'steps', value: 8000}]}
- **Then:** Response is 422 ApiError with code SERIES_NOT_FOUND; no rows inserted

### Sparkline points field is present and correctly formatted
- **Given:** The weight series has two measurements with different recorded_at timestamps (e.g. 2026-04-01 and 2026-04-05)
- **When:** GET /api/series is called
- **Then:** The weight series row contains sparkline_points field; parsed as JSON it is a list of objects each with v (float) and ts (integer, Unix epoch ms); ts values differ between the two points; ts is an integer (not a string)

### Chronos skill maps label to key successfully
- **Given:** The catalog contains an entry with key='weight', label='Weight', aliases=['body weight']
- **When:** submit_measurements is called with measurements=[{label: 'Weight', value: 80.5}]
- **Then:** The resolved key is 'weight'; a batch request is constructed with key='weight'; the API call is made with the correct payload

### Chronos skill fails on unknown label
- **Given:** The catalog does not contain any entry matching label or alias 'foo_metric'
- **When:** submit_measurements is called with measurements=[{label: 'foo_metric', value: 1.0}]
- **Then:** A CHRONOS_UNMAPPED error is raised; no API call is made
