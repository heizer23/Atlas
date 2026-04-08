# FoodTracker Sprint 05 — Reporting, UX Polish & Alcohol Tracking

## Summary

Cross-cutting polish sprint touching all four tabs. No new screens. Schema gains one column (`alcohol_g`). Report tab is the largest change.

---

## 1. Log Tab (`/food`)

### 1.1 JSON template helper (collapsible)

The log tab currently exposes a plain textarea where the user pastes JSON to describe a meal. Add a collapsible "Show template" disclosure element (collapsed by default) that reveals a copy-ready JSON template matching the current input schema. Clicking it should copy the template to the clipboard or expand it inline — expanding inline is preferred. The template must stay in sync with the actual accepted fields.

No change to the existing POST endpoint or validation logic.

### 1.2 Alcohol tracking

Add `alcohol_g NUMERIC(7,1) NOT NULL DEFAULT 0 CHECK (alcohol_g >= 0)` to `foodtracker.food_logs`.

Migration file: `migrations/004_add_alcohol.sql`.

- Include `alcohol_g` in the log JSON template (§1.1).
- Include `alcohol_g` in the preview card shown after "Log Meal" is clicked.
- Include `alcohol_g` in `GET /api/food/entries/:id` (EntryDetail response).
- Include `alcohol_g` in the edit form on `EntryDetailPage`.
- The field is optional in the log input (defaults to 0 when absent).

---

## 2. Day Tab (`/food/day`)

### 2.1 Date navigation

Currently the page always shows today's entries. Add date navigation:

- **Default:** current calendar day (unchanged).
- **Controls:** a left arrow button (previous day), a right arrow button (next day), and a date-picker input between them showing the selected date (`YYYY-MM-DD` display, native `<input type="date">`).
- The right arrow is disabled when the selected date is today.
- On date change, re-fetch `GET /api/food/day?date=YYYY-MM-DD`.

Backend change: `GET /api/food/day` must accept an optional `date` query parameter (`YYYY-MM-DD`). When absent, defaults to today (current behaviour). When present, returns today_entries for the specified date.

No change to the standards section — it always shows all standards regardless of the selected date.

---

## 3. Report Tab (`/food/report`)

### 3.1 Default scope

Change the default scope from whatever it currently is to `week`.

### 3.2 Rolling periods (replace calendar-aligned periods)

Current behaviour: "week" = Mon–Sun of the current ISO week; "month" = 1st–last of the current calendar month; "year" = Jan 1–Dec 31 of the current year.

New behaviour: all periods are **rolling** — counted backwards from today:

| Scope | Window |
|-------|--------|
| `week` | Last 7 days (today − 6 … today) |
| `month` | Last 30 days (today − 29 … today) |
| `year` | Last 365 days (today − 364 … today) |

Remove the `period_key` parameter entirely. It is no longer needed.

Keep `all_time` scope unchanged.

### 3.3 Remove column-selection outline

There is a black/dark focus outline appearing when the user clicks a column header or cell in the report table. Remove it. Use CSS `outline: none` scoped to the report table interaction elements. Do not remove focus outlines globally (accessibility).

### 3.4 Average line on year view

For scope `year`, render the chart as a **ComboChart**: stacked bars per meal type (breakfast, lunch, dinner, snack, alcohol) with a **line series overlaid showing the daily average** — computed over reported days only (see §3.5).

The line series key is `kcal_avg` (or `protein_avg` in protein view). The backend must return this value per bucket row — it is the rolling average up to and including that bucket's date, computed only over days that have entries within the year window.

Use the platform `ComboChartMapping` with `bar_mode: "stacked"` for the bar series and a `"line"` series for the average. This satisfies the ComboChart contract (≥1 bar + ≥1 line).

Other scopes (week, month) do not show the average line — they render as plain stacked BarCharts.

### 3.5 Average of reported days only

For all scopes, the displayed average must be computed **only over days that have at least one logged entry** within the window — not over the total number of calendar days in the window.

The backend must return a `reported_days` count alongside the dataset (can be a meta field or a row field). The average displayed = total ÷ reported_days.

### 3.6 Meal-type breakdown columns

Replace the current flat numeric columns (kcal, protein_g, …) in the report with **per-meal-type columns**:

Meal types to track: `breakfast`, `lunch`, `dinner`, `snack`, `alcohol`.

`alcohol` is a new pseudo-meal-type column derived from `alcohol_g > 0` entries regardless of their `meal_type`. It is NOT a new value for the `meal_type` field in `food_logs`.

The report schema columns become:

| key | label | type |
|-----|-------|------|
| `bucket_label` | Date | string |
| `kcal_breakfast` | Breakfast kcal | number |
| `kcal_lunch` | Lunch kcal | number |
| `kcal_dinner` | Dinner kcal | number |
| `kcal_snack` | Snacks kcal | number |
| `kcal_alcohol` | Alcohol kcal | number |
| `kcal_total` | Total kcal | number |
| `protein_breakfast` | Breakfast protein (g) | number |
| `protein_lunch` | Lunch protein (g) | number |
| `protein_dinner` | Dinner protein (g) | number |
| `protein_snack` | Snacks protein (g) | number |
| `protein_total` | Total protein (g) | number |

`kcal_alcohol` = sum of `kcal` for entries where `alcohol_g > 0`, within the bucket. No protein breakdown for alcohol (alcohol carries negligible dietary protein).

Retain the existing `mode` parameter (`aggregated` / `daily`) — the breakdown applies to both modes.

The frontend chart should show a stacked bar chart with one bar per meal type (breakfast, lunch, dinner, snack, alcohol), stacked to show the total. Use `bar_mode: "stacked"` with `group_by: "meal_type"` if the platform supports it; otherwise render the stacked bars directly from the breakdown columns.

The UI offers a toggle between **kcal view** and **protein view** — switching swaps which set of breakdown columns is rendered in the chart and table. Default is kcal.

---

## 4. Entries Tab (`/food/entries`)

### 4.1 Group by date

Currently all entries are rendered as a flat list. Group them by calendar date (the date portion of `logged_at`), with a sticky or non-sticky date heading above each group.

- Most recent date first.
- Within each date group, order by `logged_at` ascending (earliest meal first).
- The date heading format: full date, e.g. `Tuesday, 8 April 2026`.
- No change to the backend endpoint — grouping is done client-side from the existing response.

---

## 5. Schema changes

```sql
-- migrations/004_add_alcohol.sql
ALTER TABLE foodtracker.food_logs
  ADD COLUMN IF NOT EXISTS alcohol_g NUMERIC(7,1) NOT NULL DEFAULT 0
  CONSTRAINT food_logs_alcohol_g_nonneg CHECK (alcohol_g >= 0);
```

---

## 6. Out of scope

- Pie charts, scatter charts — not a platform primitive.
- New meal_type values — `alcohol` is a derived report column, not a new meal_type.
- Push notifications, reminders.
- Multi-user / auth changes.
- `all_time` scope changes beyond §3.3 (outline fix).
