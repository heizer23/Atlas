# FoodTracker Sprint 06 — Search, Dish Scaling, and Report Averages

## Summary

Four targeted improvements across the entries and report tabs.
No new screens. One schema migration (add `quantity_g`).
The report gets a third selectable view (alcohol in grams) alongside the existing kcal and protein views.
Average-line charting is extended to week and 30-day scopes.

---

## 1. Report Tab — Alcohol (g) View

Add a third selectable metric to the report View selector: **Alcohol (g)**. The existing "Drink" label in the kcal chart (showing kcal from alcoholic entries) is unchanged.

### 1.1 Backend change (`report.py`)

Add `alcohol_g_total` to every bucket row: `SUM(alcohol_g) AS alcohol_g_total`.

Add `alcohol_g_avg` to rows when `include_avgs=True` (computed the same way as `kcal_avg` — cumulative sum of `alcohol_g_total` ÷ cumulative `reported_days`).

Extend `REPORT_SCHEMA` with:
```python
ColumnSchema(key="alcohol_g_total", label="Alcohol (g)", type="number"),
```

Extend `_ZERO_METRICS` with `"alcohol_g_total": 0`.

The avg schema extension (year/month/week) gains:
```python
ColumnSchema(key="alcohol_g_avg", label="Avg daily alcohol (g)", type="number"),
```

### 1.2 Frontend change (`ReportPage.tsx`)

Add `'alcohol'` to the `NutMetric` type:
```tsx
type NutMetric = 'kcal' | 'protein' | 'alcohol';
```

Add a `ALCOHOL_BARS` series definition:
```tsx
const ALCOHOL_BARS = [
  { key: 'alcohol_g_total', label: 'Alcohol (g)', color: 'var(--atlas-chart-5)' },
];
```

In `AvgComboPanel` / `StackedBarPanel`, handle `metric === 'alcohol'` by using `ALCOHOL_BARS` and `avgKey = 'alcohol_g_avg'`.

Extend the View selector with a third option:
```tsx
<option value="alcohol">Alcohol (g)</option>
```

In `DataTable`, when `metric === 'alcohol'` show columns:
- `bucket_label` (Date)
- `alcohol_g_total` (Alcohol (g))
- `alcohol_g_avg` if present in rows (Avg/day)

Unit label for alcohol view: `"g"`.

---

## 2. Report Tab — Daily Average Line in Week and 30-Day Views

Currently, `kcal_avg` and `protein_avg` (rolling cumulative average over reported days only) are computed per row **only for the `year` scope**. The frontend uses a `ComboChart` for year and a plain `StackedBarChart` for week, month, and all_time.

Extend averages to `week` and `month` scopes.

### 2.1 Backend change (`report.py`)

Change `include_avgs` from `scope == "year"` to `scope in ("year", "month", "week")`.

The `_zero_fill` function already handles the rolling cumulative average computation when `include_avgs=True`. No change to the averaging logic itself.

The schema returned must also include the avg columns when scope is week or month. Use the same conditional extension already in place for year:

```python
include_avgs = (query.scope in ("year", "month", "week"))
```

The existing avg computation in `_zero_fill` is correct: it iterates bucket rows, accumulates `kcal_total` and `reported_days`, and emits `kcal_avg = cumulative_kcal / cumulative_days` (0 when no reported days yet). This same logic is correct for week and month buckets.

### 2.2 Frontend change (`ReportPage.tsx`)

Change the chart selector: use `YearComboPanel` (stacked bars + average line) for `week`, `month`, and `year` scopes. Use `StackedBarPanel` only for `all_time`.

```tsx
// Before
const isYearScope = scope === 'year';
...
isYearScope ? <YearComboPanel ... /> : <StackedBarPanel ... />

// After
const showAvgLine = scope !== 'all_time';
...
showAvgLine ? <YearComboPanel ... /> : <StackedBarPanel ... />
```

Rename `YearComboPanel` → `AvgComboPanel` (or leave the name unchanged — functionally correct as-is). The component already accepts `metric` and reads `kcal_avg` / `protein_avg` from rows — it will work for week and month rows once the backend emits those fields.

---

## 3. Entries Tab — Search-as-You-Type

Add a client-side substring search box at the top of the entries list. No backend change.

### 3.1 UI placement

Place a text input directly above the entries list, below the page header:

```
Entries
[____ search dishes ____]
<grouped entries>
```

### 3.2 Filtering behavior

- Input is controlled state: `searchQuery: string`, default `""`.
- Filter entries client-side: include entry if `entry.dish_name.toLowerCase().includes(searchQuery.toLowerCase().trim())`.
- When `searchQuery` is empty or whitespace: show all entries (no filtering).
- Filtering happens on every keystroke — no debounce needed for typical dataset sizes.
- After filtering, date grouping still applies to the filtered result set.
- Date groups with zero matching entries are omitted entirely (no empty date heading).

### 3.3 UX details

- Input placeholder: `"Search dishes…"`
- Input type: `text`
- Clear the search when the user navigates away (no persistence needed).
- No change to backend, fetch behavior, or sort order.

### 3.4 Implementation location

Add `searchQuery` and `setSearchQuery` state to `EntriesPage`. Pass filtered entries to `GroupedEntries`. No changes to `GroupedEntries` component itself — it already renders whatever `entries` array it receives. Filtering is applied in `EntriesPage` before passing to `GroupedEntries`.

---

## 4. Log Tab — Dish Quantity Scaling

Allow meals to be logged with per-100g nutrition values plus a consumed quantity in grams. The backend scales and stores the actual macro values. The consumed quantity is also stored, enabling proportional rescaling when copying an entry.

### 4.1 Schema change

Migration file: `migrations/005_add_quantity_g.sql`

```sql
ALTER TABLE foodtracker.food_logs
  ADD COLUMN IF NOT EXISTS quantity_g NUMERIC(7,1) DEFAULT NULL
  CONSTRAINT food_logs_quantity_g_pos CHECK (quantity_g IS NULL OR quantity_g > 0);
```

Nullable. `NULL` means the entry was logged with direct absolute values (existing behavior). A non-null value means the stored macros were scaled from per-100g values at log time.

Update `schema.sql` to include the column.

### 4.2 Log intake change (`food.py`)

Accept an optional top-level field `quantity_g` (positive number) in the meal JSON body.

When `quantity_g` is present and > 0:
- Treat all `nutrition.*` values as **per-100g reference values**.
- Scale before storing: `stored_value = reference_value * quantity_g / 100`.
- Apply scaling to: `calories_kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`, `good_fat_g`, `meat_g`, `red_meat_g`, `sodium_mg`, `alcohol_g`.
- Cross-field checks (`good_fat_g <= fat_g`, `red_meat_g <= meat_g`) apply to the **per-100g values** (before scaling), since the user input is at that level.
- Store `quantity_g` in the new column.

When `quantity_g` is absent:
- Existing behavior unchanged: nutrition values treated as absolute amounts.
- `quantity_g` stored as `NULL`.

Validation for `quantity_g`:
- If present: must be a number > 0. Return `VALIDATION_ERROR` with `field: "quantity_g"` if not.

### 4.3 JSON template update (`food.py`)

Add `quantity_g` to `TEMPLATE_JSON` as a commented-out optional field at the top level:

```json
{
  "timestamp": "...",
  "meal_type": "lunch",
  "quantity_g": 200,
  "items": [...],
  "nutrition": {
    "calories_kcal": 165,
    "protein_g": 31,
    ...
  }
}
```

Label the field with a comment in the template text that it represents per-100g values when provided.

### 4.4 EntryDetail API changes (`entries.py`)

**`GET /api/food/entries/:id`:** Include `quantity_g` (float or null) in the `EntryDetail` response.

Extend `_serialise_entry_detail` to include:
```python
"quantity_g": float(row["quantity_g"]) if row["quantity_g"] is not None else None,
```

**`PUT /api/food/entries/:id`:** Accept optional `quantity_g` in the `EntryEditRequest`.

In `_validate_entry_edit_request`: add an optional `quantity_g` check — when present, must be a number > 0. Store in `validated["quantity_g"]` (defaults to `None` when absent).

Update the UPDATE SQL to include `quantity_g = %s`.

### 4.5 Copy with rescale (`EntryDetailPage.tsx` and `EntriesPage.tsx`)

**Copy action** (`POST /api/food/entries/:id/copy`): When copying an entry that has `quantity_g` set, the backend copy preserves `quantity_g` (already true — the copy INSERT includes all fields; verify `quantity_g` is included in the INSERT column list in `entries.py:copy_entry`).

**`EntryDetailPage.tsx` rescale UX:** When viewing an entry with `quantity_g != null`, show a "Quantity (g)" input field in the detail view (editable). The detail page already allows editing macros. Editing `quantity_g` here should update the form values proportionally:

- Compute `per100g_kcal = entry.kcal * 100 / entry.quantity_g` (and same for other macros).
- When user changes `quantity_g` input: recompute all macro inputs as `per100g * new_quantity / 100` and update the form.
- On save (PUT), send the rescaled macro values + new `quantity_g`.

This rescale UX is opt-in (only shown when `quantity_g` is non-null on the loaded entry). Entries without `quantity_g` retain the existing flat edit form.

---

## 5. Schema changes

```sql
-- migrations/005_add_quantity_g.sql
ALTER TABLE foodtracker.food_logs
  ADD COLUMN IF NOT EXISTS quantity_g NUMERIC(7,1) DEFAULT NULL
  CONSTRAINT food_logs_quantity_g_pos CHECK (quantity_g IS NULL OR quantity_g > 0);
```

---

## 6. Out of scope

- Protein view for alcohol (no alcohol protein column exists; out of scope per Sprint 05).
- Storing per-100g values separately — they are derivable from `quantity_g` and stored macros.
- Search on the Day tab or Standards tab.
- Unit conversion (only grams supported).
- Quantity scaling for Standards (standards use absolute macro values; per-100g scaling is for ad-hoc log entries).
- Rescaling the copy via a dedicated endpoint — rescaling happens in the frontend before PUT.
