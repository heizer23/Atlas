# Test Spec — FoodTracker — Sprint06_Search_Scale_Averages

## Scope

Backend API tests for quantity_g intake scaling, entry detail/edit/copy with quantity_g, report alcohol column, and avg scope extension to week/month; UI scenarios for the alcohol view selector, average line in week/month, entry search, and quantity rescale form. Excluded: UI test execution infrastructure for EntryDetailPage rescale (manual only for this sprint), Standards tab changes (out of scope).

---

## Scenarios

### [Backend] Intake with quantity_g scales macros proportionally

- **Given:** A POST /api/food/meals body with `quantity_g: 200` and `nutrition.calories_kcal: 165`, `nutrition.protein_g: 31`
- **When:** The endpoint processes the request
- **Then:** The stored row has `calories_kcal = 330`, `protein_g = 62`, and `quantity_g = 200`

### [Backend] Intake without quantity_g stores absolute values

- **Given:** A POST /api/food/meals body with no `quantity_g` field and `nutrition.calories_kcal: 500`
- **When:** The endpoint processes the request
- **Then:** The stored row has `calories_kcal = 500` and `quantity_g = NULL`

### [Backend] Intake with invalid quantity_g returns VALIDATION_ERROR

- **Given:** A POST /api/food/meals body with `quantity_g: 0` (or a negative number)
- **When:** The endpoint processes the request
- **Then:** The response is a VALIDATION_ERROR (422) with `field: "quantity_g"`

### [Backend] Cross-field checks apply to per-100g values before scaling

- **Given:** A POST /api/food/meals body with `quantity_g: 150`, `nutrition.good_fat_g: 20`, `nutrition.fat_g: 15` (good_fat > fat in per-100g values)
- **When:** The endpoint processes the request
- **Then:** The response is a VALIDATION_ERROR; the scaled values are never stored

### [Backend] Entry detail GET includes quantity_g

- **Given:** A fixture entry with `quantity_g = 200.0`
- **When:** GET /api/food/entries/:id is called for that entry
- **Then:** The response includes `quantity_g: 200.0`

### [Backend] Entry detail GET returns null quantity_g for legacy row

- **Given:** A fixture entry with `quantity_g = NULL`
- **When:** GET /api/food/entries/:id is called for that entry
- **Then:** The response includes `quantity_g: null`

### [Backend] PUT entry accepts and stores updated quantity_g

- **Given:** A fixture entry with `quantity_g = 200.0`; a PUT /api/food/entries/:id body with `quantity_g: 250.0` and updated macro values
- **When:** The endpoint processes the request
- **Then:** The stored row has `quantity_g = 250.0` and the new macro values

### [Backend] Copy entry preserves quantity_g

- **Given:** A fixture entry with `quantity_g = 200.0`
- **When:** POST /api/food/entries/:id/copy is called
- **Then:** The new entry has `quantity_g = 200.0` and the same macro values as the source (no re-scaling)

### [Backend] Report includes alcohol_g_total in all scopes

- **Given:** At least one food_log row with `alcohol_g = 20.0` in the target period
- **When:** GET /api/food/report is called with any valid scope (year, month, week, all_time)
- **Then:** Every bucket row in the response includes `alcohol_g_total` (summed value or 0 for empty buckets)

### [Backend] Report includes avg columns for week and month scopes

- **Given:** Several food_log rows spread across different days in the target period
- **When:** GET /api/food/report is called with scope=week (and separately scope=month)
- **Then:** Each row in the response includes `kcal_avg`, `protein_avg`, and `alcohol_g_avg` fields

### [Backend] Report does not include avg columns for all_time scope

- **Given:** Any food_log rows in the database
- **When:** GET /api/food/report is called with scope=all_time
- **Then:** Row objects do not include `kcal_avg`, `protein_avg`, or `alcohol_g_avg`

### [Backend] alcohol_g_avg cumulative average is correct

- **Given:** Fixture rows: day 1 alcohol_g=10, day 2 alcohol_g=20, day 3 no log (zero-fill)
- **When:** GET /api/food/report?scope=month is called covering those days
- **Then:** Day 1 row: `alcohol_g_avg = 10.0`; day 2 row: `alcohol_g_avg = 15.0`; day 3 row: `alcohol_g_avg = 15.0` (cumulative over reported days only)

### [UI] Report view selector shows Alcohol (g) option

- **Given:** The Report page is loaded
- **When:** The user looks at the View selector
- **Then:** An "Alcohol (g)" option is visible alongside the existing Kcal and Protein options

### [UI] Report alcohol view renders chart and table

- **Given:** The Report page is loaded with data containing alcohol_g_total > 0
- **When:** The user selects "Alcohol (g)" from the View selector
- **Then:** The chart displays alcohol bars and the table shows bucket_label and Alcohol (g) columns

### [UI — manual] Report week scope shows average line

- **Given:** The Report page is loaded with scope=week and multiple days of data
- **When:** The user views the week chart
- **Then:** An average line overlay is visible on the stacked bar chart (same as the year view)

### [UI — manual] Entries search filters dish names

- **Given:** The Entries page is loaded with multiple entries having different dish names
- **When:** The user types a substring into the search input
- **Then:** Only entries whose dish_name contains the substring (case-insensitive) are shown; date groups with no matches are hidden

### [UI — manual] Entries search cleared on navigation

- **Given:** The user has entered a search term on the Entries page
- **When:** The user navigates away and back to the Entries page
- **Then:** The search input is empty and all entries are shown

### [UI — manual] Entry detail shows Quantity (g) input for scaled entries

- **Given:** An entry with quantity_g = 200 is opened in the detail view
- **When:** The user views the edit form
- **Then:** A "Quantity (g)" input field is visible showing 200

### [UI — manual] Entry detail hides Quantity (g) for unscaled entries

- **Given:** An entry with quantity_g = null is opened in the detail view
- **When:** The user views the edit form
- **Then:** No "Quantity (g)" input field is shown

### [UI — manual] Changing Quantity (g) rescales macro fields proportionally

- **Given:** An entry with quantity_g = 200 and kcal = 330 is open in the detail view
- **When:** The user changes Quantity (g) to 100
- **Then:** The kcal field updates to 165 (proportionally rescaled); other macro fields rescale proportionally
