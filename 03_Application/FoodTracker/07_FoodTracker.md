# FoodTracker Application

## Purpose
Track daily food intake as structured, queryable nutrition events.
AI-assisted: the user describes meals in natural language to ChatGPT,
which estimates nutritional values and then calls the MCP tools to record
or query the data.

## Scope
- Single-user
- AI-first input (no manual form UI)
- Postgres-backed via Atlas platform Postgres
- Tools exposed via `02_Platform/MCPGateway` (no direct HTTP exposure)

## Data Contract (Authoritative)

Schema: `02_Platform/01_Postgres/ObjectSchemas/foodtracker_schema.sql`

**Stability rule:** Code is disposable; data contracts are not.

## Tool Contract

### `log_meal` — Write
Records a single meal event.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `dish_name` | str | ✅ | Human-readable name |
| `meal_type` | str | ✅ | Prefer: breakfast / lunch / dinner / snack / other |
| `kcal` | float | ✅ | Total kilocalories |
| `protein_g` | float | ✅ | Grams of protein |
| `carbs_g` | float | ✅ | Grams of carbohydrates |
| `fat_g` | float | ✅ | Total grams of fat |
| `fiber_g` | float | ❌ | Default 0 |
| `good_fat_g` | float | ❌ | Must be ≤ fat_g. Default 0 |
| `meat_g` | float | ❌ | Default 0 |
| `red_meat_g` | float | ❌ | Must be ≤ meat_g. Default 0 |
| `sodium_mg` | float | ❌ | Default 0 |
| `confidence` | int 1–5 | ❌ | Default 3. 1=rough guess, 5=exact from label |
| `notes` | str | ❌ | Optional context |
| `logged_at` | ISO datetime str | ❌ | Defaults to now |

Returns: the inserted row.

### `get_nutrition_summary` — Read
Returns aggregated nutrition data for a date range.

| Parameter | Type | Notes |
|---|---|---|
| `from_date` | ISO date str | Inclusive, e.g. "2026-02-01" |
| `to_date` | ISO date str | Inclusive, e.g. "2026-02-22" |

Returns:
- `totals`: summed values across the period
- `daily_averages`: totals ÷ days with data
- `meals`: list of meals (summary fields)

## File Layout
```
03_Application/FoodTracker/
  tools.py          ← log_meal + get_nutrition_summary (plain functions)
  __init__.py
  07_FoodTracker.md ← this file
```

Tools are registered into `02_Platform/MCPGateway/app/main.py` at startup.
The FoodTracker module has no knowledge of the MCP protocol.
