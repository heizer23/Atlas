# Test Spec — FoodTracker — Sprint07_Base_Quantity

## Scope

Backend API tests for the quantity_g → base_quantity rename: intake with base_quantity, entry detail always returns base_quantity as non-null float, PUT edit accepts base_quantity (defaults to 100 when absent), copy preserves base_quantity. UI scenarios for the always-visible Base quantity field and rescale formula. Excluded: report tab changes (none this sprint), Standards tab changes (out of scope).

---

## Scenarios

### [Backend] Intake with base_quantity scales macros proportionally

- **Given:** A POST /api/food/meals body with `base_quantity: 200` and `nutrition.calories_kcal: 165`, `nutrition.protein_g: 31`
- **When:** The endpoint processes the request
- **Then:** The stored row has `kcal = 330`, `protein_g = 62`, and `base_quantity = 200`

### [Backend] Intake without base_quantity stores absolute values with base_quantity 100

- **Given:** A POST /api/food/meals body with no `base_quantity` field and `nutrition.calories_kcal: 500`
- **When:** The endpoint processes the request
- **Then:** The stored row has `kcal = 500` and `base_quantity = 100`

### [Backend] Intake with invalid base_quantity returns VALIDATION_ERROR

- **Given:** A POST /api/food/meals body with `base_quantity: 0` (or a negative number)
- **When:** The endpoint processes the request
- **Then:** The response is a VALIDATION_ERROR (422) with `field: "base_quantity"`

### [Backend] Entry detail GET returns base_quantity as non-null float

- **Given:** A fixture entry with `base_quantity = 200.0`
- **When:** GET /api/food/entries/:id is called for that entry
- **Then:** The response includes `base_quantity: 200.0` and does not include `quantity_g`

### [Backend] Entry detail GET returns base_quantity 100 for legacy-backfilled row

- **Given:** A fixture entry with `base_quantity = 100` (backfilled from legacy NULL)
- **When:** GET /api/food/entries/:id is called for that entry
- **Then:** The response includes `base_quantity: 100.0`

### [Backend] PUT entry accepts and stores updated base_quantity

- **Given:** A fixture entry with `base_quantity = 200.0`; a PUT /api/food/entries/:id body with `base_quantity: 250.0` and updated macro values
- **When:** The endpoint processes the request
- **Then:** The stored row has `base_quantity = 250.0` and the new macro values

### [Backend] PUT entry without base_quantity defaults to 100

- **Given:** A fixture entry; a PUT /api/food/entries/:id body with no `base_quantity` field
- **When:** The endpoint processes the request
- **Then:** The stored row has `base_quantity = 100`

### [Backend] Copy entry preserves base_quantity

- **Given:** A fixture entry with `base_quantity = 200.0`
- **When:** POST /api/food/entries/:id/copy is called
- **Then:** The new entry has `base_quantity = 200.0` and the same macro values as the source (no re-scaling)

### [UI — manual] Entry detail always shows Base quantity field

- **Given:** Any entry is opened in the detail view (regardless of original quantity_g value)
- **When:** The user views the edit form
- **Then:** A "Base quantity" input field is visible showing the current base_quantity value

### [UI — manual] Changing Base quantity rescales macro fields proportionally

- **Given:** An entry with `base_quantity = 200` and `kcal = 330` is open in the detail view
- **When:** The user changes Base quantity to 100
- **Then:** The kcal field updates to 165 (= 330 / 200 * 100); other macro fields rescale proportionally using the perUnit = stored / base_quantity formula
