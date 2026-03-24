# FoodTracker – Implementation Status

Sprint: Sprint 03 — Meal Entry Overview with Row Actions
Review date: 2026-03-23

---

## 1. Purpose

FoodTracker Sprint 03 adds a third user-facing domain to the app: entry management. Users can navigate to an Entries screen, view all stored meal entries, and act on individual rows: delete (with confirmation), copy (creates a new row and navigates to its detail), or open in a detail/edit view. The detail view loads the full field set for one entry and allows the user to save changes via a direct PUT contract that is separate from the intake flow.

---

## 2. Current Concept

The app models entry management as three independent interactions against the `foodtracker.food_logs` table:

- **List**: a read-only overview of all rows, ordered by recency, presented as a `Dataset` with a fixed overview schema.
- **Detail/Edit**: a single-row load returning a full `EntryDetail` payload, backed by a form that submits an `EntryEditRequest` directly, bypassing the intake validation path (Option A).
- **Delete**: hard delete of one row, confirmed by the user before the request is issued, with local list removal on success.
- **Copy**: server-side row duplication with a new identity and `logged_at` set to server time; the UI navigates immediately to the copied entry's detail view.

The edit flow uses a simplified contract (`EntryEditRequest`) that accepts nutrition fields and `dish_name` directly, without the intake items array. This is an explicit product decision recorded in the design artifact.

---

## 3. Current Capabilities

- Entries screen (`/food/entries`) is reachable from the FoodTracker shell navigation as the third nav item (Log order 1, Report order 2, Entries order 3), in both `mobilePrimaryNav` and `desktopNav`.
- Entries screen fetches `GET /api/food/entries` on mount and renders one card per stored meal row.
- Each row displays: `logged_at`, `meal_type`, `dish_name`, and `kcal`.
- Each row exposes three row actions: Detail (navigate to detail view), Copy, and Delete.
- Skeleton is shown while the entries list is loading.
- `ErrorCard` is shown if the initial list load fails.
- Empty state ("No meal entries logged yet.") is rendered when the entries list is empty — not treated as an error.
- Delete action opens a confirmation dialog before issuing the `DELETE` request.
- On confirmed delete success, the row is removed from the displayed list via local state (no re-fetch).
- Copy action issues `POST /api/food/entries/{id}/copy` and navigates to the copied entry's detail view on success.
- Copy errors surface through the same error display region used for delete errors.
- A `isCopying` state per entry disables the Copy button on the row being copied while in-flight.
- Entry detail view (`/food/entries/:id`) loads one entry via `GET /api/food/entries/{id}`.
- Detail view renders Skeleton while loading and `ErrorCard` on load failure.
- Detail form exposes all `EntryEditRequest` fields as editable inputs: `logged_at`, `meal_type`, `dish_name`, all nutrition fields (`kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`, `good_fat_g`, `meat_g`, `red_meat_g`, `sodium_mg`), `confidence`, and `notes`.
- System-managed fields (`id`, `created_at`, `updated_at`) are displayed read-only in a visually distinct section and are not submitted in the PUT body.
- Save action issues `PUT /api/food/entries/{id}` with an `EntryEditRequest` JSON body; no `items` array; no `id`, `created_at`, or `updated_at`.
- Save button is disabled while save is in-flight.
- Save success refreshes ENTRIES_OVERVIEW_SCHEMA fields (`logged_at`, `meal_type`, `dish_name`, `kcal`, `protein_g`, `fat_g`) from the returned Dataset row. Other form fields retain submitted values.
- A "Saved." confirmation label is displayed after a successful save.
- Save errors are displayed via `ErrorCard` below the save button.
- A Back navigation link from the detail view returns to `/food/entries`.
- Backend: `GET /api/food/entries` returns all rows from `foodtracker.food_logs` ordered by `logged_at` DESC as a `Dataset` with `ENTRIES_OVERVIEW_SCHEMA`.
- Backend: `GET /api/food/entries/{id}` returns a full `EntryDetail` dict (HTTP 200) or `ApiError` HTTP 404.
- Backend: `PUT /api/food/entries/{id}` validates an `EntryEditRequest` body inline, updates the row in-place with `updated_at = CURRENT_TIMESTAMP` explicitly in the SQL, and returns the updated row as a single-row `Dataset`.
- Backend: `DELETE /api/food/entries/{id}` hard-deletes one row using a single-statement rowcount check; returns HTTP 204 on success or `ApiError` HTTP 404 if row not found.
- Backend: `POST /api/food/entries/{id}/copy` inserts a new row with `uuid4()` id and `logged_at = datetime.now()`; returns `EntryDetail` as HTTP 201 or `ApiError` HTTP 404.
- CORS expanded to allow `GET`, `POST`, `PUT`, `DELETE`.
- `entries.py` imports nothing from `food.py` or `report.py`.
- Sprint 01 (`GET /api/food/template`, `POST /api/food/validate`, `POST /api/food/meals`) and Sprint 02 (`GET /api/food/report`) endpoints are unchanged.

---

## 4. Current Data Model

FoodTracker owns one private persistent table:

**`foodtracker.food_logs`**
Key fields: `id` (UUID), `logged_at` (TIMESTAMP WITHOUT TIME ZONE), `meal_type` (string), `dish_name` (string), `kcal` (int), `protein_g`, `carbs_g`, `fat_g`, `fiber_g`, `good_fat_g`, `meat_g`, `red_meat_g`, `sodium_mg` (float), `confidence` (int), `notes` (string nullable), `created_at` (TIMESTAMP), `updated_at` (TIMESTAMP).
Purpose: persistent store for all logged meal entries. Sprint 03 introduces the first row-level read, update, delete, and copy operations against this table. No schema changes were made in Sprint 03.

---

## 5. Contracts Consumed

- `02_Platform/01_Postgres` — Postgres instance on `atlas-net`, reachable via `ATLAS_PG_HOST:ATLAS_PG_PORT`. Schema pre-provisioned via `migrations/001_init_schema.sql`.
- `02_Platform/packages/platform_errorhandling` — `install_exception_handlers`, `install_request_timing`, `setup_logging`, `api_error()`.
- `02_Platform/packages/platform_contracts` — `ColumnSchema`, `DatasetMeta`, `Dataset` used to produce `GET /entries` and `PUT /entries/{id}` responses.
- `02_Platform/02_Atlas_Shell` — `AppRegistry.register` for shell navigation and route integration.
- `02_Platform/UI` — `apiFetch`, `isApiError`, `ErrorCard`, `Skeleton` consumed by `EntriesPage.tsx` and `EntryDetailPage.tsx`.
- `00_Blueprint/UI/07_UI_Data_Contract` — governs `Dataset` and `ApiError` response shapes for all UI-facing endpoints.

---

## 6. Interfaces Exposed

### 6.1 API Endpoints

All endpoints are served on host port 8012 (container port 8000) under prefix `/api/food`.

**`GET /api/food/entries`**
Purpose: Returns all stored meal entries for the overview list.
Input: None.
Output: `Dataset` (HTTP 200) — `object_type: food_entry`, `ENTRIES_OVERVIEW_SCHEMA` columns (`id`, `logged_at`, `meal_type`, `dish_name`, `kcal`, `protein_g`, `fat_g`), rows ordered by `logged_at` DESC. `row_actions: ["delete", "copy", "edit"]` (see conformance note in §7.3). `ApiError` HTTP 500 on unexpected error.

**`GET /api/food/entries/{id}`**
Purpose: Returns the full editable field set for one stored entry.
Input: `id` path parameter (UUID string).
Output: `EntryDetail` dict (HTTP 200) — per `architecture.json contracts.named_contracts.EntryDetail`. `ApiError` HTTP 404 if not found.

**`PUT /api/food/entries/{id}`**
Purpose: Updates an existing entry in-place using the simplified `EntryEditRequest` contract.
Input: `id` path parameter; JSON body conforming to `EntryEditRequest` (`architecture.json contracts.named_contracts.EntryEditRequest`).
Output: Single-row `Dataset` with `ENTRIES_OVERVIEW_SCHEMA` (HTTP 200). `ApiError` HTTP 404 if not found, HTTP 422 on validation failure, HTTP 400 on DB constraint violation.

**`DELETE /api/food/entries/{id}`**
Purpose: Hard-deletes one entry.
Input: `id` path parameter.
Output: HTTP 204 No Content. `ApiError` HTTP 404 if not found.

**`POST /api/food/entries/{id}/copy`**
Purpose: Creates a copy of an existing entry with a new identity and `logged_at` set to server time.
Input: `id` path parameter (source entry).
Output: `EntryDetail` dict (HTTP 201) — per `architecture.json contracts.named_contracts.EntryDetail`. `ApiError` HTTP 404 if source not found.

### 6.2 UI Datasets

**Entries overview dataset** — fetched by `EntriesPage.tsx` from `GET /api/food/entries`. Conforms to `Dataset` per `07_UI_Data_Contract`. Rows projected to `EntryRow` interface (`id`, `logged_at`, `meal_type`, `dish_name`, `kcal`, optional `protein_g`, `fat_g`).

**Entry detail dataset (PUT response)** — consumed by `EntryDetailPage.tsx` after a successful save from `PUT /api/food/entries/{id}`. Single-row `Dataset`; only ENTRIES_OVERVIEW_SCHEMA fields are used to refresh form state.

### 6.3 Events Emitted

None identified.

### 6.4 Events Consumed

None identified.

### 6.5 External / Platform Dependencies

- `fastapi` — HTTP framework (APIRouter, FastAPI, Request, JSONResponse, Response).
- `uvicorn` — ASGI server.
- `psycopg2-binary` — Postgres driver with `RealDictCursor` and `SimpleConnectionPool`.
- `pydantic` — used by `platform_contracts` for Dataset/DatasetMeta/ColumnSchema model serialisation.
- `react-router-dom` — `useNavigate`, `useParams`, `Routes`, `Route` consumed by `EntriesPage.tsx`, `EntryDetailPage.tsx`, and `ShellEntry.tsx`.

---

## 7. Known Gaps

### 7.1 Implementation Gaps

- **Save refresh is partial**: `EntryDetailPage` refreshes only the six ENTRIES_OVERVIEW_SCHEMA fields from the PUT response (`logged_at`, `meal_type`, `dish_name`, `kcal`, `protein_g`, `fat_g`). Fields such as `carbs_g`, `fiber_g`, `good_fat_g`, `meat_g`, `red_meat_g`, `sodium_mg`, `confidence`, and `notes` are not refreshed from the server response — they retain the user's submitted values. The implementation notes record this as a deliberate choice to avoid a second round-trip. However, if the server normalises or transforms any of those fields (e.g., rounding, constraint enforcement), the displayed form values will not reflect the stored values until the next page load.

- **Copy errors share delete error state**: Copy failures are surfaced through the `deleteError` state slot in `EntriesPage`. This is a deliberate implementation shortcut noted in the implementation notes. If a delete error is already displayed, a subsequent copy error will replace it without distinction.

- **No tests**: All test cases from `architecture.json deferrals.test_writer` remain unimplemented. This is an explicit deferral to the test_writer agent.

- **Sprint 01 and Sprint 02 test matrices** remain outstanding (unchanged from Sprint 02 status).

### 7.2 Inconsistencies

- **`_serialise_overview_row` is an undocumented helper**: `scaffolding.json` lists `_serialise_entry_detail` and `_validate_entry_edit_request` as the private helpers in `entries.py`. The implementation adds a third private helper `_serialise_overview_row` used by both `list_entries` and `update_entry`. This is not a functional problem, but the scaffolding document is incomplete relative to the implementation.

- **`confidence` treated as optional in validator**: The `EntryEditRequest` contract in `architecture.json` lists `confidence` as a named field with no "optional" qualifier, and the `validation_rules` section does not exempt it. The implemented `_validate_entry_edit_request` treats `confidence` as optional (defaulting to 3 if absent). Senders omitting `confidence` will silently receive a default value rather than a validation error.

- **`fiber_g`, `good_fat_g`, `meat_g`, `red_meat_g`, `sodium_mg` treated as optional in validator**: The `EntryEditRequest` contract lists all nutrition fields. The `validation_rules` in `architecture.json` call out `protein_g`, `carbs_g`, `fat_g` as required but do not explicitly mark the remaining five as optional. The validator defaults them to `0.0` if absent. Senders omitting these fields will silently write zeros to the database rather than receive a validation error.

### 7.3 Conformance Issues

- **`row_actions` value `"detail"` changed to `"edit"`**: `architecture.json` `interfaces.exposed_surfaces` and `contracts.provides` declare `row_actions: ["delete", "copy", "detail"]` for both `GET /api/food/entries` and `PUT /api/food/entries/{id}`. The deployed implementation uses `["delete", "copy", "edit"]`. This change was applied as a runtime bug fix documented in `deployment_report.md`: the Python `platform_contracts` implementation defines `RowAction = Literal["delete", "edit", "copy"]`, which rejected `"detail"` at runtime. The fix is correct for the platform as deployed, but the design artifact still declares `"detail"`. The design artifact and the implementation are misaligned. The root cause is a pre-existing inconsistency between `platform_contracts/contracts.py` and `07_UI_Data_Contract.md` (which declares `RowAction = string`). Until resolved, the deployed `row_actions` value `"edit"` does not match the designed value `"detail"`.

- **Frontend `EntriesPage` uses `"detail"` as the action label, not `"edit"`**: The Detail button in `EntriesPage.tsx` navigates to the detail view. The backend `row_actions` array now declares `"edit"`, but the frontend button label is "Detail". There is no functional problem (the frontend does not read `row_actions` to render its buttons), but the declared `row_actions` contract value and the UI label are misaligned.

### 7.4 Missing or Ambiguous Design Baseline

- **RowAction open vs closed contract**: `07_UI_Data_Contract.md` declares `RowAction = string` (open). The Python `platform_contracts` implementation uses `Literal["delete", "edit", "copy"]` (closed). This inconsistency is documented in `deployment_report.md` as a platform-level issue requiring an explicit decision. Until resolved, any sprint using a row action value outside the Python literal set will cause a runtime Pydantic rejection with no design-time signal.

---

## 8. Non-Scope

- Bulk delete or bulk copy.
- Search, filtering, sorting controls, or pagination of the entries list.
- Inline editing in the list view.
- Undo, soft delete, or audit history.
- Entry history or restore.
- Report drilldown into individual entries.
- New nutrition fields or schema changes to `foodtracker.food_logs`.
- Autosave, drafts, or conflict resolution.
- Authentication or authorization changes.
- Duplicate detection.
- Export or sharing.
- User-local timezone handling.
- Test implementation (deferred to test_writer).

---

## 9. Recommendation

### Recommended Owner

Implementer

### Reason

The Sprint 03 implementation is functionally complete and deployed. The primary outstanding items are: (1) the `row_actions` conformance issue, which requires a platform-level decision before the design artifact and implementation can be aligned; and (2) the partial save refresh in `EntryDetailPage`, which is a known implementation limitation that may surface stale form values for non-schema nutrition fields after save.

### Suggested Next Action

Two parallel actions:

1. Resolve the `RowAction` open/closed contract inconsistency at the platform level (`platform_contracts/contracts.py` vs `07_UI_Data_Contract.md`). Once resolved, update `entries.py` `row_actions` and `architecture.json` to use the agreed canonical value for the "open detail" action.

2. Evaluate whether `EntryDetailPage` should re-fetch `GET /api/food/entries/{id}` after a successful PUT to ensure all displayed fields reflect stored values. The current partial refresh is acceptable if no server-side transformation occurs on the non-schema nutrition fields, but this assumption is not enforced anywhere.

### Priority

Medium — the app is functional. The `row_actions` misalignment is cosmetic for the current single-user context but is a latent contract correctness issue for any future consumer.

---

## Validation Warnings

- **Confirmed mismatch with explicit design artifact**: `architecture.json` declares `row_actions: ["delete", "copy", "detail"]`. The deployed implementation uses `["delete", "copy", "edit"]` in both `list_entries` and `update_entry`. The change is documented as a deliberate bug fix in `deployment_report.md`, but the design artifact has not been updated to reflect the deployed state.

- **Missing contract where an explicit artifact requires one**: The `RowAction` type is declared as open (`string`) in `07_UI_Data_Contract.md` but is closed (`Literal`) in the Python platform implementation. These two sources are in direct contradiction. Any new sprint that introduces a row action outside the Python enum will fail at runtime without a design-time warning.

- **Capability without full implementation evidence**: The detail view save refresh only updates ENTRIES_OVERVIEW_SCHEMA fields from the PUT response. Architecture specifies "overview reflects the updated summary values" on save success — this is met for the overview schema fields. However, non-schema fields displayed in the form are not refreshed from the authoritative stored state after save, which is a partial implementation of the save-refresh behavior described in the draft.
