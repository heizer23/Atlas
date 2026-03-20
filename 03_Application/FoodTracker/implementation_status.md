# FoodTracker – Implementation Status

## 1. Purpose

FoodTracker records and queries daily food intake as structured, queryable nutrition events. Input is AI-assisted: a user describes meals in natural language to an LLM (ChatGPT), which estimates nutritional values and invokes MCP tools to write or read data. There is no manual form UI.

## 2. Current Concept

The app models nutrition as discrete meal events (`food_logs` rows), each capturing macro and micronutrient estimates alongside a confidence score and optional notes. All writes and reads are exposed as MCP tools registered into the platform MCPGateway. The app has no HTTP server of its own; it is a pure domain module composed into the gateway at startup.

## 3. Current Capabilities

- Log a single meal event with required macros (kcal, protein, carbs, fat) and optional fields (fiber, good fat, meat, red meat, sodium, confidence, notes, timestamp). Inserts a UUID-keyed row into `foodtracker.food_logs` and returns the inserted row.
- Query aggregated nutrition totals and daily averages for a caller-specified inclusive date range. Returns period metadata, summed totals for all tracked fields, daily averages (divided by days with data), and a lightweight per-meal summary list ordered by timestamp.
- Schema is managed via the Atlas migration runner. Two migrations are applied: initial schema creation (`001_init_schema.sql`) and an idempotent migration to move any legacy data from `public.food_logs` to `foodtracker.food_logs` (`002_move_public_food_logs.sql`).

## 4. Current Data Model

**`foodtracker.food_logs`**

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `logged_at` | TIMESTAMP | When the meal occurred; NOT NULL |
| `meal_type` | TEXT | Free text; preferred values: breakfast, lunch, dinner, snack, other; NOT NULL |
| `dish_name` | TEXT | Human-readable name; NOT NULL |
| `kcal` | NUMERIC(7,0) | Total kilocalories; DEFAULT 0 |
| `protein_g` | NUMERIC(7,1) | Grams of protein; DEFAULT 0 |
| `carbs_g` | NUMERIC(7,1) | Grams of carbohydrates; DEFAULT 0 |
| `fiber_g` | NUMERIC(7,1) | Grams of fiber; DEFAULT 0 |
| `fat_g` | NUMERIC(7,1) | Total grams of fat; DEFAULT 0 |
| `good_fat_g` | NUMERIC(7,1) | Unsaturated fat; DEFAULT 0; CHECK good_fat_g <= fat_g |
| `meat_g` | NUMERIC(7,1) | Total meat; DEFAULT 0 |
| `red_meat_g` | NUMERIC(7,1) | Red meat subset; DEFAULT 0; CHECK red_meat_g <= meat_g |
| `sodium_mg` | NUMERIC(7,0) | Sodium in milligrams; DEFAULT 0 |
| `confidence` | SMALLINT | 1–5 quality indicator; DEFAULT 3; CHECK BETWEEN 1 AND 5 |
| `notes` | TEXT | Optional free-text context; nullable |
| `created_at` | TIMESTAMP | Row creation timestamp; DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | Row last-updated timestamp; DEFAULT CURRENT_TIMESTAMP (not auto-updated by trigger) |

Indexes: `idx_food_logs_logged_at` (logged_at), `idx_food_logs_meal_type` (meal_type).

## 5. Contracts Consumed

- **Atlas Platform Postgres** (`02_Platform/01_Postgres`): connection via `ATLAS_PG_*` environment variables (host, port, dbname, user, password). Migration tracking via `public.schema_migrations`.
- **Atlas MCPGateway** (`02_Platform/MCPGateway`): FoodTracker registers `log_meal` and `get_nutrition_summary` as MCP tools at gateway startup. Gateway owns the MCP protocol and Google OAuth authentication; FoodTracker has no protocol dependency.

## 6. Interfaces Exposed

### 6.1 API Endpoints

None identified. The app exposes no HTTP endpoints directly.

### 6.2 UI Datasets

None identified. There is no UI for this application.

### 6.3 Events Emitted

None identified.

### 6.4 Events Consumed

None identified.

### 6.5 External / Platform Dependencies

- `02_Platform/01_Postgres`: Postgres database for all persistent state.
- `02_Platform/MCPGateway`: MCP tool registration and transport. FoodTracker tools are imported directly into the gateway process at startup (`main.py`).
- `fastmcp` (Python package): consumed by the gateway, not directly by FoodTracker.
- `psycopg[binary]` (Python package): consumed directly by FoodTracker for Postgres access.

## 7. Known Gaps

- **Schema location mismatch**: The definition states the authoritative schema lives at `02_Platform/01_Postgres/ObjectSchemas/foodtracker_schema.sql`. That path does not exist. The actual schema is maintained via migrations at `03_Application/FoodTracker/migrations/001_init_schema.sql` with a reference copy at `03_Application/FoodTracker/schema.sql`. The definition's stated schema location is a non-conformance against the definition artifact.
- **`updated_at` not auto-maintained**: The `updated_at` column exists in the table but there is no trigger to update it on row modification. Since `log_meal` does not perform updates this is currently benign, but the column is misleading if rows are ever updated manually.
- **Hardcoded DB host**: `tools.py` connects to `host="127.0.0.1"`. This works because MCPGateway runs in `network_mode: host`, but it creates a tight coupling to the host-networking topology. The definition does not specify connection approach, so this is not a definition violation; it is an infrastructure fragility.
- **File layout in definition is inaccurate**: The definition's File Layout section references `07_FoodTracker.md` as the definition file. No file by that name exists; the definition is at `03_Application/FoodTracker/00_Requirements/00_Definition.md`. This is an internal inconsistency within the definition artifact.
- **`get_nutrition_summary` meal list omits several fields**: The returned meal summary excludes fiber_g, good_fat_g, meat_g, red_meat_g, sodium_mg, and notes. The definition states "summary fields only" without enumerating them, so the current selection is not a confirmed violation, but the omission of fields is not documented anywhere.
- **No input validation in `log_meal` before DB insert**: The relational constraints (good_fat_g <= fat_g, red_meat_g <= meat_g, confidence BETWEEN 1 AND 5) are enforced only at the database layer. A violated constraint will raise an unhandled psycopg exception that propagates to the MCP caller without a structured error response. The definition does not specify error handling behavior, so this is recorded as a gap rather than a violation.
- **No design baseline for error handling**: The definition specifies tool return values for the success case only. There is no specified behavior for constraint violations, connection failures, or invalid input. Conformance cannot be evaluated for error paths.

## 8. Non-Scope

- No HTTP API surface (no REST or GraphQL endpoints).
- No UI of any kind.
- No authentication or authorization logic (delegated entirely to MCPGateway).
- No multi-user support; the app is single-user by definition.
- No meal editing or deletion capability.
- No scheduling, alerting, or notification behavior.
- No cross-application data sharing via shared views or contracts; FoodTracker data is private to the `foodtracker` schema.

## 9. Recommendation

### Recommended Owner

Implementer

### Reason

The two defined tools are fully implemented and match the definition's tool contract. The primary outstanding issues are infrastructure (hardcoded host, missing schema at the defined path) and internal definition inconsistencies, not missing features.

### Suggested Next Action

1. Resolve the schema location discrepancy: either move `schema.sql` to `02_Platform/01_Postgres/ObjectSchemas/foodtracker_schema.sql` as the definition specifies, or update the definition to reflect the migrations-based approach as authoritative.
2. Correct the File Layout section of the definition to reference the actual file path.
3. Evaluate whether the `host="127.0.0.1"` assumption should be replaced with a configurable `ATLAS_PG_HOST` env var for topology resilience.

### Priority

Low

---

## Validation Warnings

- **Schema location mismatch against explicit design artifact**: The definition (`00_Requirements/00_Definition.md`) declares `02_Platform/01_Postgres/ObjectSchemas/foodtracker_schema.sql` as the authoritative schema. This path does not exist in the repository. The schema is maintained via migrations in `03_Application/FoodTracker/migrations/` with a local reference copy in `03_Application/FoodTracker/schema.sql`.
- **Definition internal inconsistency**: The File Layout section of the definition names `07_FoodTracker.md` as the definition file. This file does not exist. The definition is at `03_Application/FoodTracker/00_Requirements/00_Definition.md`.
