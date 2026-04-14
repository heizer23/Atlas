# FoodTracker Sprint 07 — Base Quantity Reuse

## Summary

Rename `quantity_g` to `base_quantity` and give it a clearer, unified meaning:
the quantity that the stored nutrition values refer to. Every entry always has
a `base_quantity`. Rescaling when reusing an entry works via a single formula
regardless of whether the entry is gram-based or serving-based.

No new screens. One schema migration. Changes touch the migration file,
`schema.sql`, `food.py`, `entries.py`, and `EntryDetailPage.tsx`.

---

## 1. Semantics

`base_quantity` is the reference quantity for the stored nutrition values.

- Gram-based entry: `base_quantity = 200` means "these macros are for 200 g".
- Serving-based entry: `base_quantity = 1` means "these macros are for 1 serving
  (1 bar, 1 bottle, 1 glass — implied by the dish name)".

Rescaling formula (uniform for both kinds):

```
new_macro = stored_macro / base_quantity × new_base_quantity
```

The distinction between gram-based and serving-based is conveyed by dish naming
convention only. No separate column or type flag is introduced.

---

## 2. Schema migration (`migrations/006_rename_quantity_g.sql`)

```sql
BEGIN;

-- Backfill: legacy entries that were logged without a quantity reference
-- get base_quantity = 100. This is a placeholder meaning "macros as entered".
-- The user will replace specific entries by hand over time if needed.
UPDATE foodtracker.food_logs
  SET quantity_g = 100
  WHERE quantity_g IS NULL;

-- Rename column
ALTER TABLE foodtracker.food_logs
  RENAME COLUMN quantity_g TO base_quantity;

-- Make non-nullable; default 100 for future inserts that omit the field
ALTER TABLE foodtracker.food_logs
  ALTER COLUMN base_quantity SET NOT NULL,
  ALTER COLUMN base_quantity SET DEFAULT 100;

-- Replace constraint (old name referenced quantity_g)
ALTER TABLE foodtracker.food_logs
  DROP CONSTRAINT food_logs_quantity_g_pos;

ALTER TABLE foodtracker.food_logs
  ADD CONSTRAINT food_logs_base_quantity_pos CHECK (base_quantity > 0);

COMMIT;
```

---

## 3. `schema.sql` update

Replace the `quantity_g` column block with:

```sql
  -- Base quantity (Sprint 07)
  -- The quantity that the stored nutrition values refer to.
  -- Gram-based entries: grams consumed. Serving-based entries: serving count (usually 1).
  -- Rescaling: new_macro = stored_macro / base_quantity × new_base_quantity.
  -- Default 100: legacy entries use this placeholder until manually corrected.
  base_quantity NUMERIC(7,1) NOT NULL DEFAULT 100,
```

Replace constraint `food_logs_quantity_g_pos` with:

```sql
  CONSTRAINT food_logs_base_quantity_pos CHECK (base_quantity > 0)
```

---

## 4. `food.py` changes

### 4.1 Template JSON

Replace `quantity_g` with `base_quantity` in `TEMPLATE_JSON`. Update the
note in the `notes` field:

```json
{
  "timestamp": "...",
  "meal_type": "lunch",
  "base_quantity": 200,
  "items": [...],
  "nutrition": {
    "calories_kcal": 165,
    ...
  },
  "notes": "nutrition values are per 100 units of base_quantity; omit base_quantity to log absolute values (base_quantity defaults to 100)"
}
```

### 4.2 Validation (step 9, `_validate_and_normalise`)

Rename `quantity_g` → `base_quantity` throughout the validation step and
the normalised output dict. Behavior is unchanged:

- When `base_quantity` is present and > 0: scale all nutrition fields by
  `base_quantity / 100` before storing.
- When absent: default to `100` (no scaling; stored values equal input values).

The docstring comment for step 9 becomes:

```
9. optional top-level base_quantity: number > 0 if present; when present,
   scale all nutrition.* as stored_value = ref_value * base_quantity / 100.
   When absent, base_quantity defaults to 100 (values stored as-is).
```

### 4.3 INSERT statement

Replace `quantity_g` with `base_quantity` in the column list and parameter tuple.

---

## 5. `entries.py` changes

### 5.1 `_serialise_entry_detail`

Replace:
```python
"quantity_g": float(row["quantity_g"]) if row["quantity_g"] is not None else None,
```
With:
```python
"base_quantity": float(row["base_quantity"]),
```

`base_quantity` is always non-null after the migration.

### 5.2 `_validate_entry_edit_request`

Rename step 10 from `quantity_g` to `base_quantity`. Change from optional
to required: if absent from the PUT body, default to `100` (preserves
backwards compatibility). Validation: must be a number > 0.

The validated dict key becomes `"base_quantity"`.

### 5.3 UPDATE SQL

Replace `quantity_g = %s` with `base_quantity = %s`.

### 5.4 `copy_entry` INSERT

Replace `quantity_g` in the column list and `source.get("quantity_g")` with
`source["base_quantity"]` in the parameter tuple.

---

## 6. `EntryDetailPage.tsx` changes

### 6.1 Types

In `EntryDetail`: replace `quantity_g: number | null` with `base_quantity: number`.

In `EntryFormState`: replace `quantity_g: number | null` with `base_quantity: number`.

### 6.2 `entryToFormState`

Replace:
```ts
quantity_g: entry.quantity_g ?? null,
```
With:
```ts
base_quantity: entry.base_quantity,
```

### 6.3 Per-unit reference state

Rename `per100g` state to `perUnit`. Change the computation from
`stored * 100 / quantity_g` to simply `stored / base_quantity`:

```ts
const [perUnit, setPerUnit] = useState<Record<string, number> | null>(null);
```

In the `useEffect` load handler, always compute `perUnit` (not gated on
`!= null`):

```ts
const q = detail.base_quantity;
setPerUnit({
  kcal:       detail.kcal       / q,
  protein_g:  detail.protein_g  / q,
  carbs_g:    detail.carbs_g    / q,
  fat_g:      detail.fat_g      / q,
  fiber_g:    detail.fiber_g    / q,
  good_fat_g: detail.good_fat_g / q,
  meat_g:     detail.meat_g     / q,
  red_meat_g: detail.red_meat_g / q,
  sodium_mg:  detail.sodium_mg  / q,
  alcohol_g:  detail.alcohol_g  / q,
});
```

### 6.4 Base quantity change handler

Rename `handleQuantityChange` to `handleBaseQuantityChange`. Change the
rescale formula from `perUnit[field] * newQty / 100` to `perUnit[field] * newQty`:

```ts
function handleBaseQuantityChange(newQty: number) {
  setSaveError(null);
  setSaveSuccess(false);
  if (!perUnit || newQty <= 0) {
    setFormState((prev) => prev ? { ...prev, base_quantity: newQty } : prev);
    return;
  }
  setFormState((prev) => {
    if (!prev) return prev;
    return {
      ...prev,
      base_quantity: newQty,
      kcal:       Math.round(perUnit['kcal']       * newQty),
      protein_g:  Math.round(perUnit['protein_g']  * newQty * 10) / 10,
      carbs_g:    Math.round(perUnit['carbs_g']    * newQty * 10) / 10,
      fat_g:      Math.round(perUnit['fat_g']      * newQty * 10) / 10,
      fiber_g:    Math.round(perUnit['fiber_g']    * newQty * 10) / 10,
      good_fat_g: Math.round(perUnit['good_fat_g'] * newQty * 10) / 10,
      meat_g:     Math.round(perUnit['meat_g']     * newQty * 10) / 10,
      red_meat_g: Math.round(perUnit['red_meat_g'] * newQty * 10) / 10,
      sodium_mg:  Math.round(perUnit['sodium_mg']  * newQty * 10) / 10,
      alcohol_g:  Math.round(perUnit['alcohol_g']  * newQty * 10) / 10,
    };
  });
}
```

### 6.5 Field display

Remove the `{formState.quantity_g !== null && (...)}` guard. The
"Base quantity" field is always shown for every entry:

```tsx
<FieldRow label="Base quantity">
  <input
    type="number"
    value={formState.base_quantity}
    min={0.1}
    step="1"
    onChange={(e) => handleBaseQuantityChange(parseFloat(e.target.value) || 0)}
    style={inputStyle}
    title="Changing base quantity rescales all macro values proportionally"
  />
</FieldRow>
```

### 6.6 `_buildPutBody`

Replace `quantity_g: formState.quantity_g` with `base_quantity: formState.base_quantity`.

---

## 7. Out of scope

- Changes to the report tab or standards tab.
- Any UI to distinguish gram-based vs serving-based entries — naming convention
  is sufficient.
- Validation that `base_quantity` is integer for serving-based entries.
- Storing per-unit reference values separately in the database.
