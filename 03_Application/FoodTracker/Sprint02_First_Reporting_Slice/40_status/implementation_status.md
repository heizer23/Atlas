# FoodTracker – Implementation Status

## 1. Purpose

FoodTracker provides two user-facing capabilities over the `foodtracker.food_logs` table: a user-mediated JSON meal intake flow (Sprint 01) and a nutritional reporting screen with time-scoped column charts, drill navigation, and server-side bucket aggregation (Sprint 02). No writes occur without explicit user confirmation via the intake flow. The reporting endpoint is strictly read-only.

## 2. Current Concept

The application models two distinct interaction domains over a single private table.

The intake domain models a meal event as a structured JSON payload. The backend validates and normalises the payload statelessly — no intermediate state is persisted between the validate and commit calls. The frontend manages a three-state flow (idle → preview → success) as a single React component.

The reporting domain models nutritional data as time-bucketed aggregations. The backend owns all aggregation and bucket-generation logic, returning a `Dataset` whose rows each represent one time bucket (day, week, month, or year) containing all five supported metric columns. The frontend manages page-level scope, period, mode, and drill-navigation state and renders two independently configured chart panels over the same Dataset. Metric switching within a loaded Dataset does not trigger a backend call.

Both domains share the `foodtracker.food_logs` table (pre-provisioned via migrations) and the same backend process on port 8012.

## 3. Current Capabilities

**Intake (Sprint 01 — unchanged)**

- Returns a hardcoded canonical meal JSON template as `text/plain` via `GET /api/food/template`. Template content is a module-level constant, not read from disk or database.
- Accepts a raw JSON payload for validation via `POST /api/food/validate`. Runs eight ordered validation checks, applies normalisation (defaults, `dish_name` derivation by joining `items[].name` with `", "`, `kcal` rounded to integer, timestamp re-serialised as `"YYYY-MM-DDTHH:MM:SS"`, unknown fields stripped), and returns a typed preview model on success or a structured `ApiError` on any failure.
- Accepts the same raw JSON payload for commit via `POST /api/food/meals`. Re-runs full validation and normalisation independently (no shared state with the validate call), inserts one row into `foodtracker.food_logs`, and returns the inserted row wrapped in a `Dataset` conforming to the UI data contract.
- Handles `psycopg2.errors.CheckViolation` and `psycopg2.IntegrityError` at the commit endpoint and returns `ApiError` with code `DB_CONSTRAINT` and HTTP 400.
- Unexpected exceptions caught by `install_exception_handlers` return `ApiError` with code `INTERNAL_ERROR` and HTTP 500.
- Frontend renders three distinct states: idle (template display, copy button, paste area, "Log Meal" trigger), preview (all 14 normalised fields in a `<dl>`, "Back" and "Accept" controls), and success (confirmation of `logged_at`, `meal_type`, `dish_name`, `kcal` with "Log Another" reset).
- Template is fetched on component mount via `GET /api/food/template` with a `Skeleton` displayed while loading. On load failure, an `ErrorCard` is rendered in place of the template area.
- Paste textarea is a controlled component; content is preserved on validation error. The form never resets on error.
- "Log Meal" button is disabled when the paste area is empty and during in-flight requests. "Accept" button is disabled during in-flight requests.
- "Back" from preview returns to idle with pasted JSON preserved. "Log Another" from success returns to idle and clears the textarea.

**Reporting (Sprint 02)**

- Accepts scope (`all_time | year | month | week`), optional `period_key`, and `mode` (`aggregated | daily`) query parameters via `GET /api/food/report`.
- Validates all three parameters server-side before any DB query. Rejects `mode=aggregated` when `scope=week` with `INVALID_PARAM`. Rejects misformatted `period_key` with `INVALID_PERIOD_KEY`. Rejects absent `period_key` for non-`all_time` scopes with `INVALID_PARAM`.
- Executes server-side GROUP BY aggregation over `foodtracker.food_logs` with SUM across five metric columns (`kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`). GROUP BY expression uses ISO-correct `to_char(logged_at,'IYYY-"W"IW')` for `month+aggregated`, matching the YYYY-WNN bucket id format.
- Generates zero-fill bucket rows for all periods within the selected scope with no logged entries. Zero-fill covers: daily mode for all scopes with a defined period boundary (year, month, week), and aggregated mode for year, month scopes. For `all_time+aggregated`, returns only years present in DB results (no synthetic zero-fill for years with no data). For `all_time+daily`, returns only DB result rows without zero-fill (no period boundary exists).
- Returns a `Dataset` where `meta.object_type = "food_report_bucket"`, every row contains all five metric columns, `id = bucket_id`, and `bucket_label` is the display string for the x-axis.
- `REPORT_SCHEMA` column order: `bucket_label`, `kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g` — conforming to the sprint definition Data Contract schema order.
- `DatasetMeta.label` is a human-readable string in the format `"<Period Display> — <Mode Display>"` (e.g., `"March 2025 — Daily"`, `"All Time — Aggregated"`, `"Week 12, 2025 — Daily"`).
- `GET /api/food/report` never writes to `foodtracker.food_logs`.
- Frontend `ReportPage` owns all page-level state: `scope`, `period_key`, `mode`, `navStack`, `topMetric`, `bottomMetric`, `currentDataset`, `isLoading`, `error`.
- Default state on first load: `scope=month`, `period_key=current YYYY-MM`, `mode=daily`. Top chart defaults to `protein_g`; bottom chart defaults to `kcal`.
- Fetches `GET /api/food/report` on mount and on any scope, `period_key`, or mode change. Metric changes within the current Dataset do not trigger a fetch.
- Scope selector navigates to the system-current period for the selected scope and clears `navStack`.
- Mode selector is hidden (not disabled) when `scope=week`.
- Back button is visible and enabled when `navStack` is non-empty. Pops and restores the previous scope/period/mode, triggering a fetch.
- Drill navigation: bar click in aggregated mode pushes current state onto `navStack` and navigates to the drilled period. Drill targets: `all_time→year`, `year→month`, `month→week`. Week is the deepest scope. Drill is not available in daily mode.
- Two `ChartPanel` instances rendered vertically, each with an independent metric selector (local component state) and a recharts `BarChart` with `x=bucket_label`, `y=<selected metric>`. y-axis scaling is independent per chart.
- Metric selector options in display order: Protein, Calories, Carbohydrates, Fat, Fiber. Duplicate metric selection across the two panels is permitted.
- `Skeleton` rendered while `isLoading=true`. `ErrorCard` rendered if `error` is non-null.
- `report.py` imports nothing from `food.py`; the two routers share no module-level state.
- Server time choice: `datetime.now()` (local server time) is used for current-period resolution. This is documented in `report.py` module docstring.

**Shell and Infrastructure**

- Shell registration: `appId: 'food'`, `basePath: '/food'`, `mobilePrimaryNav` and `desktopNav` each contain two nav items: `{ id: 'log', label: 'Log', path: '/food', order: 1 }` and `{ id: 'report', label: 'Report', path: '/food/report', order: 2 }`. `secondaryMenu` is empty.
- Backend starts via Docker Compose at `127.0.0.1:8012` on the `atlas-net` external network. CORS allows `GET POST` only.
- `tools.py` (legacy MCP tool module) is not imported anywhere in the backend package.

## 4. Current Data Model

**`foodtracker.food_logs`** — private application table, `foodtracker` schema

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key; generated server-side as `uuid4()` |
| `logged_at` | TIMESTAMP | When the meal occurred; NOT NULL |
| `meal_type` | TEXT | One of: breakfast, lunch, dinner, snack, other; NOT NULL |
| `dish_name` | TEXT | Derived server-side by joining `items[].name` with `", "`; NOT NULL |
| `kcal` | NUMERIC(7,0) | Total kilocalories; rounded to integer before insert; DEFAULT 0 |
| `protein_g` | NUMERIC(7,1) | Grams of protein; DEFAULT 0 |
| `carbs_g` | NUMERIC(7,1) | Grams of carbohydrates; DEFAULT 0 |
| `fiber_g` | NUMERIC(7,1) | Grams of fiber; DEFAULT 0 |
| `fat_g` | NUMERIC(7,1) | Total grams of fat; DEFAULT 0 |
| `good_fat_g` | NUMERIC(7,1) | Unsaturated fat; DEFAULT 0; DB CHECK good_fat_g <= fat_g |
| `meat_g` | NUMERIC(7,1) | Total meat; DEFAULT 0 |
| `red_meat_g` | NUMERIC(7,1) | Red meat subset; DEFAULT 0; DB CHECK red_meat_g <= meat_g |
| `sodium_mg` | NUMERIC(7,0) | Sodium in milligrams; DEFAULT 0 |
| `confidence` | SMALLINT | 1–5 quality indicator; DEFAULT 3; DB CHECK BETWEEN 1 AND 5 |
| `notes` | TEXT | Optional free-text context; nullable |
| `created_at` | TIMESTAMP | Row creation timestamp; DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | Last-updated timestamp; DEFAULT CURRENT_TIMESTAMP; no update trigger |

Indexes: `idx_food_logs_logged_at` (logged_at), `idx_food_logs_meal_type` (meal_type).

Schema provisioned via `migrations/001_init_schema.sql`. Migration `002_move_public_food_logs.sql` is an idempotent data migration for environments with a legacy `public.food_logs` table. No schema changes in Sprint 02.

## 5. Contracts Consumed

- **`02_Platform/01_Postgres`**: Postgres instance on `atlas-net` reachable via `ATLAS_PG_HOST:ATLAS_PG_PORT`. Accessed via `psycopg2-binary` with `SimpleConnectionPool` and `RealDictCursor`. Connection built from `ATLAS_PG_*` env vars (`DATABASE_URL` env var accepted as override).
- **`02_Platform/packages/platform_errorhandling`**: `install_exception_handlers`, `install_request_timing`, `setup_logging`, and `api_error()` constructor consumed by the backend.
- **`02_Platform/packages/platform_contracts`**: `ColumnSchema`, `DatasetMeta`, `Dataset` consumed by the commit endpoint and the report endpoint to produce UI data contract–conformant responses.
- **`02_Platform/02_Atlas_Shell`**: `AppRegistry.register` consumed by `src/shellConfig.ts` to register the `/food` route and nav entries.
- **`02_Platform/UI`**: `apiFetch`, `isApiError`, `ErrorCard`, `Skeleton` consumed by `src/ShellEntry.tsx` and `src/ReportPage.tsx`.

## 6. Interfaces Exposed

### 6.1 API Endpoints

**`GET /api/food/template`**
- Purpose: Returns the hardcoded canonical meal JSON template for the user to copy into an external LLM.
- Input: None.
- Output: `text/plain` body containing the raw JSON template string. HTTP 200.

**`POST /api/food/validate`**
- Purpose: Validates and normalises a raw meal JSON payload; returns a preview model for user review without writing to the database.
- Input: Raw JSON body conforming to the meal input contract (timestamp, meal_type, items, nutrition, optional fields).
- Output: `{"preview": { ... }}` (HTTP 200) with all 14 normalised fields, or `ApiError` (HTTP 422) with `code: "VALIDATION_ERROR"` and `detail.reason` containing the specific failure category.

**`POST /api/food/meals`**
- Purpose: Validates, normalises, and commits a meal entry; returns the inserted row.
- Input: Same raw JSON body as the validate endpoint.
- Output: `Dataset` (HTTP 200) with `meta.object_type: "food_meal"`, `MEAL_SCHEMA` (14 columns), and the single inserted row; or `ApiError` HTTP 422 (validation failure), HTTP 400 (`DB_CONSTRAINT`), HTTP 500 (`INTERNAL_ERROR`).

**`GET /api/food/report`**
- Purpose: Accepts scope, period_key, and mode query parameters; queries `foodtracker.food_logs` with server-side aggregation and zero-fill bucket generation; returns a Dataset where each row is one time bucket containing all five metric columns.
- Input: `scope` (required: `all_time | year | month | week`), `period_key` (required for non-`all_time` scopes; format varies by scope), `mode` (required: `aggregated | daily`).
- Output: `Dataset` (HTTP 200) with `meta.object_type: "food_report_bucket"`, `REPORT_SCHEMA` (6 columns), N bucket rows; or `ApiError` HTTP 422 (`INVALID_PARAM`, `INVALID_PERIOD_KEY`), HTTP 500 (`INTERNAL_ERROR`).

### 6.2 UI Datasets

**Commit response dataset** — consumed by `ShellEntry.tsx` success handler.
- Source endpoint: `POST /api/food/meals`
- `meta.object_type`: `food_meal`
- Schema keys (in order): `logged_at`, `meal_type`, `dish_name`, `kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`, `good_fat_g`, `meat_g`, `red_meat_g`, `sodium_mg`, `confidence`, `notes`
- The frontend extracts only `logged_at`, `meal_type`, `dish_name`, and `kcal` from the first row for the success panel. The full Dataset shape is not rendered in a table view.

**Report dataset** — consumed by `ReportPage.tsx` for chart rendering.
- Source endpoint: `GET /api/food/report`
- `meta.object_type`: `food_report_bucket`
- Schema keys (in order): `bucket_label`, `kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`
- Each row also carries `id` (the stable bucket identifier, e.g. `"2025-03-01"`). `id` is used by `ChartPanel` to identify the drill target on bar click; `bucket_label` is used as the x-axis display value.
- Both chart panels consume the same Dataset instance. Metric selection is local component state within each `ChartPanel` and does not trigger a refetch.

### 6.3 Events Emitted

None identified.

### 6.4 Events Consumed

None identified.

### 6.5 External / Platform Dependencies

- `fastapi`: HTTP framework; `APIRouter`, `FastAPI`, `Request`, `Query`, `PlainTextResponse`, `JSONResponse`.
- `uvicorn`: ASGI server.
- `psycopg2-binary`: Postgres driver. Connection pooling via `SimpleConnectionPool`.
- `pydantic`: Response model serialisation (`Dataset.model_dump`).
- `recharts`: Chart library. `BarChart`, `Bar`, `XAxis`, `YAxis`, `CartesianGrid`, `Tooltip`, `ResponsiveContainer` consumed by `ReportPage.tsx`. Declared as already present in the atlas-shell external libraries.

## 7. Known Gaps

### 7.1 Implementation Gaps

- No tests exist. The `deferrals.test_writer` section in `component_architecture.json` (both Sprint 01 and Sprint 02) defines an explicit test matrix spanning intake endpoint success and failure cases, report endpoint scope/mode/period combinations, zero-fill correctness, and constraint validation. No test files, test runner configuration, or test directory are present in the repository.

### 7.2 Inconsistencies

- `ShellEntry.tsx` uses relative route paths `path="/"` and `path="/report"` within its nested `<Routes>` block. The `component_scaffold.json` specifies absolute paths `path='/food'` and `path='/food/report'`. The relative path implementation is functionally correct given the shell mounts the component at `/food`, so React Router resolves `"/"` to `/food` and `"/report"` to `/food/report`. However it diverges from the scaffold specification and may cause confusion if the shell mount point changes. This also means the Sprint 01 wildcard issue (`path="/*"`) is resolved in practice — `path="/"` within a nested router does not match all sub-paths the way `path="/*"` did.
- `FoodIntake` is exported as a named export from `ShellEntry.tsx`. The scaffold's `public_objects` entry for `FoodIntake` was retained from Sprint 01 with no declared consumer outside the file. This is a low-impact observation (unchanged from Sprint 01).
- `apiFetch` in `ShellEntry.tsx` is used to fetch the `text/plain` template response. `apiFetch` JSON-parses all responses; the plain-text JSON body is parsed by the client and then re-serialised with `JSON.stringify(res, null, 2)` for display. The template displayed to the user is re-formatted with 2-space indentation rather than preserving the exact whitespace of the backend constant `TEMPLATE_JSON`. This is unchanged from Sprint 01.
- The `updated_at` column in `foodtracker.food_logs` has no update trigger. Rows inserted by the intake flow will always have `updated_at` equal to `created_at`. Unchanged from Sprint 01.
- `_currentPeriodKey` in `ReportPage.tsx` uses browser `Date` (client-side clock) to determine the current period for the scope selector and initial load. The `component_architecture.json` deferred decision notes "server time for this slice" with `datetime.now()` used on the backend. If the client's local date differs from the server's date (e.g., near midnight across timezones), the frontend-computed `period_key` for the default state may not match the server's current period. The sprint definition defers "user-local timezone handling" as out of scope, but the discrepancy is present and undocumented.
- Drill navigation from `month+aggregated` scope: when a user clicks a week bucket (bucket id `YYYY-WNN`), `handleDrillDown` sets `period_key = bucketId` and `scope = 'week'`. The `GET /api/food/report` call will then be issued with `scope=week&period_key=YYYY-WNN&mode=daily`. This is correct. However, the drill target mode is set to `'daily'` for `week` scope only; the transition from `year+aggregated` to `month` scope sets `targetMode = 'aggregated'` (not `'daily'`), meaning the drilled month view opens in aggregated mode rather than daily mode. The sprint definition states "daily is the default" but the drill path description does not specify what mode the drilled period opens in. This behaviour is an unspecified implementation decision.
- `tools.py` remains in the repository. It is not imported anywhere in the backend package. If the MCPGateway still imports it, two independent write paths to `foodtracker.food_logs` remain simultaneously active. The Sprint 02 `component_architecture.json` explicitly lists `tools.py` as forbidden for import in the backend.

### 7.3 Conformance Issues

- `component_scaffold.json` specifies `ShellEntry.tsx`'s default export renders `<Route path='/food' element={<FoodIntake />} />` using absolute paths. The implementation uses relative paths (`path="/"` and `path="/report"`). Functionally equivalent in the current shell mount configuration, but diverges from the scaffold's explicit path specification.
- The sprint definition §7.3 CORS surface note (carried from Sprint 01) listed `DELETE` as an allowed method. The `component_architecture.json` corrected this to `GET POST` only. The implementation uses `GET POST` only, conforming to the design artifact. The sprint definition text was not updated to remove `DELETE`. The design artifact takes precedence; this is recorded for traceability.

### 7.4 Missing or Ambiguous Design Baseline

- No test baseline exists. `deferrals.test_writer` in `component_architecture.json` defines expected test cases but there is no test runner configuration, test directory, or test files. Conformance of test coverage cannot be evaluated.
- The `DATABASE_URL` environment variable fallback in `database.py` is not declared in `compose.yml` or in the design contracts. Its behaviour is inherited from the WorkoutTracker pattern. If a future environment injects `DATABASE_URL`, it will silently override the `ATLAS_PG_*` values.
- The drill mode transition behaviour (what mode a drilled period opens in) is not specified in the sprint definition or design artifacts. The implementation opens drilled `month` scope in `aggregated` mode and drilled `week` scope in `daily` mode. This cannot be evaluated for conformance.
- The `_build_report_label` week format (`"Week 12, 2025 — Daily"`) was flagged in the design review as a low-risk scaffold-only observation with no example provided. The implementation uses this format, which cannot be confirmed as conformant since the design artifact did not specify it.

## 8. Non-Scope

- Editing or deleting existing meal entries.
- Batch or multi-meal JSON imports.
- Authentication or authorization logic.
- Goals, targets, nutritional recommendations, or completeness indicators.
- Period-over-period comparisons or comparison overlays.
- Arbitrary custom date ranges.
- Export or share.
- Table-first reporting UI or meal-level drilldown.
- User-local timezone handling.
- Mobile-specific refinements beyond the current layout.
- Prefetching or background loading of alternate report states.
- Client-side aggregation from raw meal rows.
- New platform components or shared capabilities.
- MCP-based meal input (the legacy `tools.py` MCP path remains but is separate from the implemented backend).

## 9. Recommendation

### Recommended Owner

Implementer

### Reason

Both Sprint 01 and Sprint 02 scopes are fully implemented. All four API endpoints are present and behaviorally complete. The reporting backend correctly implements aggregation, zero-fill, bucket generation, and parameter validation. The frontend reporting page implements scope/mode/period controls, drill navigation, back navigation, two independent chart panels, and the no-refetch-on-metric-change constraint. Shell navigation is updated with the Report nav item. The primary outstanding items are missing tests (no test files at all despite an explicit test matrix), minor route path inconsistency between implementation and scaffold, and the undocumented client-vs-server time discrepancy in period key resolution.

### Suggested Next Action

1. Add test files per the `deferrals.test_writer` matrices in `component_architecture.json` for both Sprint 01 and Sprint 02. Priority: Sprint 02 report endpoint correctness tests (zero-fill, scope/mode combinations, `INVALID_PARAM` for `week+aggregated`, chronological ordering of rows).
2. Clarify the drill mode transition decision (what mode a drilled period opens in) and record it as a resolved decision in the design artifact or implementation notes, so it is not treated as a gap in future reviews.
3. Update the sprint definition §7.3 to remove `DELETE` from the CORS methods list, resolving the documented artifact inconsistency.

### Priority

Medium

---

## Validation Warnings

- No test files present despite explicit `deferrals.test_writer` test matrices defined in `component_architecture.json` for both Sprint 01 and Sprint 02.
- `ShellEntry.tsx` route paths (`path="/"`, `path="/report"`) diverge from `component_scaffold.json` specification (`path='/food'`, `path='/food/report'`). Functionally equivalent under current shell mount; confirmed mismatch with explicit scaffold artifact.
- `foodtracker.food_logs` is read by `GET /api/food/report` but only the five aggregated metric columns (`kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`) are surfaced in the report Dataset. Other table columns (`good_fat_g`, `meat_g`, `red_meat_g`, `sodium_mg`, `confidence`, `notes`) are not exposed by any read interface. This is consistent with the sprint definition's defined metric set and is recorded for awareness.
- Sprint definition §7.3 CORS surface lists `DELETE`; implementation uses `GET POST` only. Implementation conforms to `component_architecture.json`. Sprint definition requires a correction by the Manager.
- Client-side `_currentPeriodKey` (browser `Date`) used for default period resolution and scope selector navigation. Backend uses `datetime.now()` (server local time). No design artifact specifies how the client determines the current period; timezone mismatch is possible near day boundaries. No explicit design baseline to evaluate against.
