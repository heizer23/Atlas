# Implementation Notes — Sprint 03: Meal Entry Overview with Row Actions

## Implementer
- application-implementer
- Date: 2026-03-21

## Scope Implemented

All items from `architecture.json` `deferrals.application_implementer` and `deferrals.ui_implementer`.

---

## Backend Changes

### New file: `backend/routers/entries.py`

Sprint 03 entry management module. Fully independent — imports nothing from `food.py` or `report.py`.

**Key design decisions:**

1. **Option A: EntryEditRequest contract for PUT**
   PUT `/api/food/entries/{id}` accepts `{logged_at, meal_type, dish_name, kcal, protein_g, carbs_g, fat_g, fiber_g, good_fat_g, meat_g, red_meat_g, sodium_mg, confidence, notes?}`. dish_name is user-submitted directly. The inline validator `_validate_entry_edit_request` does not call or reference `_validate_and_normalise` from food.py.

2. **DELETE single-statement approach**
   `DELETE FROM foodtracker.food_logs WHERE id = %s`, then check `cursor.rowcount`. If `rowcount == 0`, rollback and return 404. No prior SELECT.

3. **`updated_at` explicit in PUT SQL**
   `SET ... updated_at = CURRENT_TIMESTAMP` in the UPDATE statement. No trigger dependency.

4. **`ENTRIES_OVERVIEW_SCHEMA` column order**
   `id, logged_at, meal_type, dish_name, kcal` (required order per design). `protein_g` and `fat_g` added as `detail_visible=True` for richer display.

5. **`list_entries` SELECT optimisation**
   Only fetches ENTRIES_OVERVIEW_SCHEMA columns from the DB (not `SELECT *`), since the overview endpoint does not need the full detail field set. This differs from `get_entry` and `copy_entry` which use `SELECT *`.

6. **`_serialise_entry_detail` datetime handling**
   Uses `hasattr(val, 'strftime')` guard for the naive datetime objects psycopg2 returns for `TIMESTAMP WITHOUT TIME ZONE` columns. Consistent with existing pattern in food.py.

**Deviations from scaffolding:**

- `copy_entry`: The two `with conn.cursor() as cur` blocks are in separate sequential `with` statements under a single `with get_db() as conn` block. The source check and INSERT are kept as separate cursor contexts so that an early `return` on NOT_FOUND exits cleanly before the INSERT cursor is opened.

### Modified file: `backend/main.py`

Changes (only two lines added, one expanded):
- Import: `from backend.routers import food, report, entries`
- Register: `app.include_router(entries.router, prefix='/api')`
- CORS: `allow_methods=['GET', 'POST', 'PUT', 'DELETE']`

food.py and report.py are untouched.

---

## Frontend Changes

### Modified: `src/shellConfig.ts`

Added `{ id: 'entries', label: 'Entries', path: '/food/entries', order: 3 }` to both `mobilePrimaryNav` and `desktopNav`. Existing Log (order 1) and Report (order 2) entries unchanged.

### Modified: `src/ShellEntry.tsx`

Added imports for `EntriesPage` and `EntryDetailPage`. Added two routes:
- `<Route path="/entries" element={<EntriesPage />} />`
- `<Route path="/entries/:id" element={<EntryDetailPage />} />`

Existing `/` and `/report` routes unchanged.

### New file: `src/EntriesPage.tsx`

- Fetches GET `/food/entries` on mount.
- Renders each entry row with `logged_at`, `meal_type`, `dish_name`, `kcal`.
- Three row actions per entry: **Detail** (navigate), **Copy** (POST copy endpoint, navigate to new id), **Delete** (confirmation dialog).
- `DeleteConfirmDialog` is a private component rendered via portal-like fixed overlay using CSS position:fixed.
- Empty state: "No meal entries logged yet." (not an error).
- Error and loading states handled with `ErrorCard` and `Skeleton`.
- `isCopying` state tracks which row is in-flight for copy to disable the Copy button.
- Delete and copy errors are surfaced through the same `deleteError` state slot (copy errors are rare and share the same display region at top of page).

### New file: `src/EntryDetailPage.tsx`

- Reads `id` from `useParams()`.
- Fetches GET `/food/entries/:id` on mount.
- `entryToFormState` maps `EntryDetail` to `EntryFormState` on load.
- `_buildPutBody` constructs the EntryEditRequest JSON body. `notes` is omitted from the body if empty string (backend treats absence as `null`).
- After save, form state is refreshed from the returned Dataset row — only ENTRIES_OVERVIEW_SCHEMA fields (the overview columns) are updated from the response; other form fields retain their submitted values (server echoes them back in the DB row via RETURNING * but the dataset only includes overview columns).
- Read-only display: `id`, `created_at`, `updated_at` in a visually distinct section.
- dish_name is a user-editable text input (Option A).
- Back link navigates to `/food/entries`.

**TypeScript notes:**
- `FieldRow` and `ReadOnlyField` are local helper components for consistent label/input layout.
- `React.CSSProperties` typing for the `inputStyle` constant.

---

## Conformance to Architecture

| Invariant | Status |
|-----------|--------|
| entries.py imports nothing from food.py or report.py | Confirmed |
| PUT uses EntryEditRequest, not validate_and_normalise | Confirmed |
| PUT sets updated_at = CURRENT_TIMESTAMP explicitly | Confirmed |
| DELETE returns HTTP 204 No Content | Confirmed |
| DELETE uses single-statement rowcount check | Confirmed |
| POST copy assigns new uuid4() id | Confirmed |
| POST copy sets logged_at = datetime.now() | Confirmed |
| CORS expanded to GET POST PUT DELETE | Confirmed |
| nav order: Log=1, Report=2, Entries=3 | Confirmed |
| Empty entries list renders empty state (not error) | Confirmed |
| Delete shows confirmation dialog before DELETE call | Confirmed |
| Copy navigates to copied entry detail on success | Confirmed |
| PUT body has no id, created_at, updated_at | Confirmed |
| dish_name is user-editable in edit form | Confirmed |

---

## Known Gaps / Deferral Notes

- Tests deferred to test_writer per architecture.json.
- Sprint 01 and Sprint 02 test matrices remain outstanding (unchanged from Sprint 02 status).
- `EntryDetailPage` save refresh only updates ENTRIES_OVERVIEW_SCHEMA fields from the returned row. A full refresh would require re-fetching GET `/food/entries/:id` after save — this is not done to avoid a second round-trip. The form still reflects the user's submitted values for non-schema fields.
