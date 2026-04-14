# FoodTracker — Architecture Exceptions

This file registers approved deviations from Blueprint-level rules for the FoodTracker application.
Governed by R-CON-BP-05 §3 (APPLICATION-scope exceptions are local and not centrally registered).

---

## EXC-FT-01 — DayPagePayload: composed dashboard shape for GET /food/day

**RULE_ID:** EXC-FT-01
**EXCEPTION_TO:** R-CON-BP-04 (UI Data Contract)
**SCOPE:** APPLICATION (FoodTracker)
**STATUS:** ACTIVE
**ENDPOINTS:** `GET /api/food/day`

**Deviation:** Returns `DayPagePayload` — a composed nested structure `{ today_entries: [...], standards: [...] }` — instead of `Dataset`.

**Rationale:** The Day page is a composed dashboard whose primary content is two independent collections rendered side-by-side. These collections have different semantics and cannot be expressed as a single paginated Dataset without either discarding structure or creating an artificial join. The shape is a "composed dashboard payload" as permitted by R-CON-BP-04 §Default-First Rule.

**Named contract:** `DayPagePayload` as declared in `Sprint04_Standard Dishes/20_design/architecture.json` under `contracts.named_contracts`.

**Fields:**
- `today_entries`: list of `{ id, logged_at, meal_type, dish_name, kcal, protein_g, fat_g, standard, source_standard_id }`
- `standards`: list of `{ id, dish_name, kcal, protein_g, fat_g, today_instance_id }`

---

## EXC-FT-02 — StandardsPagePayload: composed shape for GET /food/standards

**RULE_ID:** EXC-FT-02
**EXCEPTION_TO:** R-CON-BP-04 (UI Data Contract)
**SCOPE:** APPLICATION (FoodTracker)
**STATUS:** ACTIVE
**ENDPOINTS:** `GET /api/food/standards`

**Deviation:** Returns `StandardsPagePayload` — `{ standards: [...], today_instances: [...] }` — instead of `Dataset`.

**Rationale:** The Standards page displays a combined view of standard dishes and their today-instance status. These are semantically distinct lists. A Dataset would require either redundant denormalization or loss of the today-instance linkage. This is a "detail object with nested structure" and "composed dashboard payload" as permitted by R-CON-BP-04.

**Named contract:** `StandardsPagePayload` as declared in `Sprint04_Standard Dishes/20_design/architecture.json`.

---

## EXC-FT-03 — Command results for Standards mutation endpoints

**RULE_ID:** EXC-FT-03
**EXCEPTION_TO:** R-CON-BP-04 (UI Data Contract)
**SCOPE:** APPLICATION (FoodTracker)
**STATUS:** ACTIVE
**ENDPOINTS:**
- `POST /api/food/standards/{id}/log` — returns HTTP 201 with `EntryDetail`
- `PATCH /api/food/entries/{id}/standard` — returns `{ id, standard }`
- `DELETE /api/food/standards/{id}/today-instance` — returns HTTP 204 (no body)

**Deviation:** These mutation endpoints return command results rather than Dataset.

**Rationale:** These are command endpoints (log, toggle, delete) that return confirmation of the action performed. R-CON-BP-04 explicitly permits non-Dataset shapes for "a command result" and "a form definition or submission result." Dataset is not a natural fit for mutation confirmations.

**Named contracts:**
- `EntryDetail`: `{ id, logged_at, meal_type, dish_name, kcal, protein_g, carbs_g, fiber_g, fat_g, good_fat_g, meat_g, red_meat_g, sodium_mg, confidence, notes, standard, source_standard_id, base_quantity }` as declared in `Sprint04_Standard Dishes/20_design/architecture.json` and updated in Sprint07_Base_Quantity. `base_quantity` is `float` (non-null) — the quantity that the stored nutrition values refer to; defaults to 100 for legacy entries.
- `StandardToggleResult`: `{ id: string, standard: boolean }`
- HTTP 204: no body; success is indicated by status code.

---

## EXC-FT-04 — EntryDetail shape for GET /food/entries/{id}

**RULE_ID:** EXC-FT-04
**EXCEPTION_TO:** R-CON-BP-04 (UI Data Contract)
**SCOPE:** APPLICATION (FoodTracker)
**STATUS:** ACTIVE
**ENDPOINTS:** `GET /api/food/entries/{id}`

**Deviation:** Returns a bare `EntryDetail` object rather than a single-row `Dataset`.

**Rationale:** This is a detail endpoint for a single entry, consumed by the entry edit form. R-CON-BP-04 permits non-Dataset shapes for "a detail object with nested structure." A single-row Dataset would add artificial pagination metadata with no semantic value for a by-ID lookup.

**Named contract:** `EntryDetail` as defined in EXC-FT-03 above.

---

## EXC-FT-05 — PreviewPayload shape for POST /food/validate

**RULE_ID:** EXC-FT-05
**EXCEPTION_TO:** R-CON-BP-04 (UI Data Contract)
**SCOPE:** APPLICATION (FoodTracker)
**STATUS:** ACTIVE
**ENDPOINTS:** `POST /api/food/validate`

**Deviation:** Returns `{ preview: <normalised_entry_dict> }` — a validation/preview result — instead of `Dataset`.

**Rationale:** This is a form validation endpoint that returns a normalised preview of what would be stored if the user confirms. R-CON-BP-04 explicitly permits non-Dataset shapes for "a form definition or submission result." The `preview` key wraps the normalised entry to distinguish it from a committed row.

**Named contract:** `PreviewPayload`: `{ preview: <normalised_entry_dict> }` where the entry dict matches the normalised field structure of a `food_logs` row.
