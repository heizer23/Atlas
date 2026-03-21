## Status

Draft — ready for Designer

## Owner

Manager

---

## 1. Purpose

Restore end-to-end meal logging without MCP by introducing a minimal, explicit, user-mediated JSON intake flow.

The user manually transfers structured meal data between ChatGPT and FoodTracker.
FoodTracker validates, previews, and commits the data into the existing database.

This slice establishes a working vertical path:
User → ChatGPT → JSON → FoodTracker → Database

---

## 2. Slice Scope

### Included

- Minimal FoodTracker GUI for meal input
- JSON template generation
- JSON paste input
- Validation and parsing of payload
- Human-readable preview of parsed data
- Explicit user acceptance step
- Insert into `foodtracker.food_logs`
- Success and error feedback

### Excluded

- Viewing historical meals
- Editing or deleting entries
- Batch imports (multi-meal JSON)
- Authentication redesign
- Analytics or aggregation features
- MCP-based input

---

## 3. User Flow

1. User opens FoodTracker input page
2. User clicks "Generate Template"
3. System displays the canonical JSON template
4. User copies template into ChatGPT
5. ChatGPT returns filled JSON
6. User pastes JSON into FoodTracker
7. System validates and parses input
8. System displays preview of normalised data
9. User clicks "Accept"
10. System writes one row to database
11. System displays success or structured error

---

## 4. Core Design Principles

### 4.1 Explicit User Control

No automatic writes. All persistence requires explicit user confirmation.

### 4.2 No Hidden Durable State

- No draft storage in database
- No background persistence
- Temporary state exists only in browser memory

### 4.3 Contract-First Input

JSON format is strict and canonical. Input must match the defined schema before acceptance.

### 4.4 Single Responsibility

One JSON payload = one meal event. No batching or implicit splitting.

### 4.5 Preview = Truth

Preview reflects the validated and normalised data, not raw JSON. Exactly what will be written to the DB.

---

## 5. Data Contract (Input JSON)

### 5.1 Canonical Template

The template displayed to the user via "Generate Template":

```json
{
  "timestamp": "2026-03-20T12:30:00",
  "meal_type": "lunch",
  "items": [
    {
      "name": "chicken breast",
      "quantity": 200,
      "unit": "g"
    }
  ],
  "nutrition": {
    "calories_kcal": 450,
    "protein_g": 50,
    "carbs_g": 20,
    "fat_g": 10,
    "fiber_g": 5,
    "good_fat_g": 0,
    "meat_g": 0,
    "red_meat_g": 0,
    "sodium_mg": 0
  },
  "confidence": 4,
  "notes": "estimated from description"
}
```

This template is hardcoded in the backend and returned verbatim by `GET /api/food/template`. It is not user-configurable.

### 5.2 Field Rules

| Field | Type | Required | Constraints |
|---|---|---|---|
| `timestamp` | string | Yes | ISO-8601 datetime; e.g. `"2026-03-20T12:30:00"` |
| `meal_type` | string | Yes | One of: `breakfast`, `lunch`, `dinner`, `snack`, `other` |
| `items` | array | Yes | At least one element; each element must have `name` (string) |
| `items[].name` | string | Yes | Non-empty string |
| `items[].quantity` | number | No | If present, must be `> 0` |
| `items[].unit` | string | No | Free text |
| `nutrition.calories_kcal` | number | Yes | `≥ 0` |
| `nutrition.protein_g` | number | Yes | `≥ 0` |
| `nutrition.carbs_g` | number | Yes | `≥ 0` |
| `nutrition.fat_g` | number | Yes | `≥ 0` |
| `nutrition.fiber_g` | number | No | `≥ 0`; defaults to `0` |
| `nutrition.good_fat_g` | number | No | `≥ 0`, `≤ fat_g`; defaults to `0` |
| `nutrition.meat_g` | number | No | `≥ 0`; defaults to `0` |
| `nutrition.red_meat_g` | number | No | `≥ 0`, `≤ meat_g`; defaults to `0` |
| `nutrition.sodium_mg` | number | No | `≥ 0`; defaults to `0` |
| `confidence` | integer | No | `1`–`5`; defaults to `3` |
| `notes` | string | No | Free text; nullable |

All numeric values must be numbers (not strings). Unknown fields at the top level and inside `nutrition` are ignored. Unknown fields inside `items` entries are ignored.

### 5.3 Mapping to `foodtracker.food_logs`

| JSON field | DB column | Notes |
|---|---|---|
| `timestamp` | `logged_at` | Parsed with `datetime.fromisoformat()` |
| `meal_type` | `meal_type` | Trimmed |
| `items[0].name` (or joined names if multiple) | `dish_name` | If multiple items: join with `", "` |
| `nutrition.calories_kcal` | `kcal` | Cast to integer |
| `nutrition.protein_g` | `protein_g` | |
| `nutrition.carbs_g` | `carbs_g` | |
| `nutrition.fat_g` | `fat_g` | |
| `nutrition.fiber_g` | `fiber_g` | Default `0` |
| `nutrition.good_fat_g` | `good_fat_g` | Default `0` |
| `nutrition.meat_g` | `meat_g` | Default `0` |
| `nutrition.red_meat_g` | `red_meat_g` | Default `0` |
| `nutrition.sodium_mg` | `sodium_mg` | Default `0` |
| `confidence` | `confidence` | Default `3` |
| `notes` | `notes` | Nullable |

`id` is generated server-side as `uuid.uuid4()`. `created_at` and `updated_at` are set by the DB default.

---

## 6. System Behaviour

### 6.1 Template Generation (`GET /api/food/template`)

Returns the canonical JSON template as a `text/plain` response body (the raw JSON string). The frontend displays it in a pre-formatted, selectable text area so the user can copy it.

### 6.2 Validation Layer (`POST /api/food/validate`)

Accepts `Content-Type: application/json` with the pasted payload body.

**Validation checks (in order):**
1. Body is syntactically valid JSON — if not, return `PARSE_ERROR`
2. `timestamp` is present and parseable as ISO-8601 datetime — if not, `INVALID_FIELD`
3. `meal_type` is present and is one of the allowed values — if not, `INVALID_FIELD`
4. `items` is a non-empty array and each item has a non-empty `name` — if not, `INVALID_FIELD`
5. `nutrition` object is present — if not, `MISSING_FIELD`
6. `nutrition.calories_kcal`, `protein_g`, `carbs_g`, `fat_g` are present and are numbers `≥ 0` — if not, `INVALID_FIELD`
7. Optional numeric fields are numbers if present and satisfy their constraints — if not, `INVALID_FIELD`
8. `confidence` if present is an integer between 1 and 5 — if not, `INVALID_FIELD`

On any failure: return `ApiError` (HTTP 422) with the structure:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "<human-readable summary of first failure>",
    "detail": { "field": "<dot-path>", "reason": "<why>" },
    "request_id": "<8-char hex>"
  }
}
```

On success: return the normalised preview model (see §6.4). HTTP 200.

### 6.3 Normalisation

Applied after successful validation, before returning the preview:
- Apply defaults for all optional numeric fields (`0`) and `confidence` (`3`)
- Derive `dish_name` from `items`
- Cast `calories_kcal` to integer
- Parse `timestamp` to a Python `datetime` and re-serialise as `"YYYY-MM-DDTHH:MM:SS"` for the preview
- Strip unknown fields

### 6.4 Preview Model

The validate endpoint returns this JSON shape on success:

```json
{
  "preview": {
    "logged_at": "2026-03-20T12:30:00",
    "meal_type": "lunch",
    "dish_name": "chicken breast",
    "items": [
      { "name": "chicken breast", "quantity": 200, "unit": "g" }
    ],
    "kcal": 450,
    "protein_g": 50.0,
    "carbs_g": 20.0,
    "fat_g": 10.0,
    "fiber_g": 5.0,
    "good_fat_g": 0.0,
    "meat_g": 0.0,
    "red_meat_g": 0.0,
    "sodium_mg": 0.0,
    "confidence": 4,
    "notes": "estimated from description"
  }
}
```

This is not a `Dataset` — it is a preview-specific shape private to this sprint's flow. The frontend renders it directly, not via `TableView`.

### 6.5 Commit (`POST /api/food/meals`)

Accepts the same JSON payload as the validate endpoint (the original pasted JSON, not the preview). Runs the same validation internally. On success, inserts one row into `foodtracker.food_logs` and returns the inserted row as a `Dataset`.

**Why re-validate on commit:** The UI sends the original JSON again. The server does not store any intermediate state between validate and commit. This satisfies the no-hidden-durable-state principle.

**Dataset response shape on success:**

```python
Dataset(
    meta=DatasetMeta(
        object_type="food_meal",
        label="Food Log",
        total=1, page=1, page_size=1,
        row_actions=[],
    ),
    schema_=MEAL_SCHEMA,   # see §8
    rows=[inserted_row],   # id as text, logged_at as text, all numeric fields as float
)
```

**Error responses:**
- Validation failure: `ApiError` code `VALIDATION_ERROR`, HTTP 422 (same structure as validate endpoint)
- Database constraint violation (e.g. `good_fat_g > fat_g` slipping through): `ApiError` code `DB_CONSTRAINT`, HTTP 400
- Unexpected exception: caught by `install_exception_handlers`, returns `ApiError` code `INTERNAL_ERROR`, HTTP 500

### 6.6 Feedback

**Success:** The UI replaces the paste area with a confirmation panel showing logged_at, meal_type, dish_name, and kcal from the returned row. A "Log Another" button resets the form.

**Error:** `ErrorCard` rendered inside the form area. The pasted JSON and the paste area remain visible so the user can correct and resubmit. The form never resets on error.

---

## 7. Architecture

### 7.1 Backend — new files

```
03_Application/FoodTracker/
  backend/
    __init__.py
    main.py
    database.py
    routers/
      __init__.py
      food.py
  pyproject.toml
  Dockerfile
  compose.yml
  logs/          (created at runtime)
```

The existing `tools.py`, `migrations/`, and `schema.sql` are not modified. The backend does not import `tools.py` (the `127.0.0.1` hardcoding in `tools.py` would break inside the Docker network; see Known Constraints §9.1).

### 7.2 Backend — API surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/food/template` | Return canonical JSON template as `text/plain` |
| `POST` | `/api/food/validate` | Validate and normalise; return preview or `ApiError` |
| `POST` | `/api/food/meals` | Validate, insert, return `Dataset` or `ApiError` |

No GET for meal list. No DELETE. Those are deferred to Sprint 02.

### 7.3 Backend — implementation patterns

**`database.py`:** Copy WorkoutTracker `database.py` verbatim. Reads `ATLAS_PG_*` env vars. Exposes `init_pool()` and `get_db()`. Uses `psycopg2-binary` with `RealDictCursor`.

**`main.py`:** Follow WorkoutTracker `main.py` verbatim:
- `FastAPI(title="FoodTracker", version="0.1.0")`
- CORS: `allow_origin_regex=r"http://localhost:\d+"`, methods `GET POST`, header `Content-Type`
- `install_exception_handlers(app)`, `install_request_timing(app)`
- `setup_logging(app_name="foodtracker", log_dir=...)`
- Startup: `init_pool()`
- Router: `food.router`, prefix `"/api"`

**`pyproject.toml`:**
```toml
[project]
name = "food-tracker"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["fastapi", "uvicorn", "psycopg2-binary", "pydantic"]

[tool.setuptools]
packages = ["backend"]
```

**`Dockerfile`:** Follow WorkoutTracker Dockerfile verbatim, substituting `FoodTracker` for `WorkoutTracker`. Do not copy `foodtracker/tools.py` — only `backend/` is needed.

**`compose.yml`:**
```yaml
services:
  food-tracker:
    container_name: atlas-food-tracker
    build:
      context: ../..
      dockerfile: 03_Application/FoodTracker/Dockerfile
    restart: unless-stopped
    ports:
      - "127.0.0.1:8012:8000"
    environment:
      ATLAS_PG_DB:       ${ATLAS_PG_DB}
      ATLAS_PG_USER:     ${ATLAS_PG_USER}
      ATLAS_PG_PASSWORD: ${ATLAS_PG_PASSWORD}
      ATLAS_PG_PORT:     ${ATLAS_PG_PORT}
      ATLAS_PG_HOST:     atlas-postgres
    volumes:
      - ${DATA_ROOT}/food-tracker/logs:/app/logs
    networks:
      - atlas-net

networks:
  atlas-net:
    external: true
```

### 7.4 Dataset column schema (used by `POST /api/food/meals` response)

```python
MEAL_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="logged_at",  label="Date / Time",   type="date",   sortable=True),
    ColumnSchema(key="meal_type",  label="Meal",           type="string", sortable=True,  filterable=True),
    ColumnSchema(key="dish_name",  label="Dish",           type="string", sortable=True),
    ColumnSchema(key="kcal",       label="kcal",           type="number", sortable=True,  format="kcal"),
    ColumnSchema(key="protein_g",  label="Protein (g)",    type="number", sortable=True,  format="g"),
    ColumnSchema(key="carbs_g",    label="Carbs (g)",      type="number", sortable=True,  format="g"),
    ColumnSchema(key="fat_g",      label="Fat (g)",        type="number", sortable=True,  format="g"),
    ColumnSchema(key="fiber_g",    label="Fiber (g)",      type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="good_fat_g", label="Good Fat (g)",   type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="meat_g",     label="Meat (g)",       type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="red_meat_g", label="Red Meat (g)",   type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="sodium_mg",  label="Sodium (mg)",    type="number", sortable=False, detail_visible=True),
    ColumnSchema(key="confidence", label="Confidence",     type="number", sortable=True),
    ColumnSchema(key="notes",      label="Notes",          type="string", sortable=False, detail_visible=True),
]
```

### 7.5 Frontend — new files

```
03_Application/FoodTracker/
  src/
    shellConfig.ts
    ShellEntry.tsx
```

### 7.6 Shell registration (`shellConfig.ts`)

```typescript
AppRegistry.register({
  appId: 'food',
  label: 'Food',
  basePath: '/food',
  component: React.lazy(() => import('./ShellEntry')),

  mobilePrimaryNav: [
    { id: 'log', label: 'Log', path: '/food', order: 1 },
  ],

  desktopNav: [
    { id: 'log', label: 'Log', path: '/food', order: 1 },
  ],

  secondaryMenu: [],
});
```

### 7.7 `ShellEntry.tsx` — component design

Single route: `/food` → `FoodIntake` component.

`FoodIntake` manages three distinct UI states:

| State | Renders |
|---|---|
| `idle` | Template display + paste area + "Log Meal" button |
| `preview` | Preview panel + "Accept" button + "Back" button |
| `success` | Confirmation panel + "Log Another" button |

**State transitions:**

```
idle
 ├── user clicks "Generate Template" → fetch GET /api/food/template; display in text area
 ├── user pastes JSON into textarea → no automatic action (user-driven)
 └── user clicks "Log Meal"
       → POST /api/food/validate with textarea content
       ├── ApiError → stay in idle; render ErrorCard below the paste area
       └── success (preview data) → transition to preview state

preview
 ├── user clicks "Back" → return to idle; preserve pasted JSON in textarea
 └── user clicks "Accept"
       → POST /api/food/meals with the same pasted JSON
       ├── ApiError → stay in preview; render ErrorCard below the preview panel
       └── success → transition to success state

success
 └── user clicks "Log Another" → return to idle; clear textarea
```

**Idle state render:**
1. Page heading: "Log a Meal"
2. A pre-formatted, selectable `<textarea readonly>` or `<pre>` showing the template (fetched on mount via `GET /api/food/template`; shows a loading skeleton while fetching)
3. "Copy Template" button — copies the template text to clipboard
4. A `<textarea>` labelled "Paste filled JSON here" — controlled component, user types/pastes here
5. "Log Meal" filled button — triggers validate; disabled while request is in-flight
6. If an `ApiError` is present: `<ErrorCard>` rendered below the button

**Preview state render:**
1. Heading: "Preview — does this look right?"
2. Read-only field list showing all normalised values (logged_at, meal_type, dish_name, kcal, protein_g, carbs_g, fat_g, fiber_g, good_fat_g, meat_g, red_meat_g, sodium_mg, confidence, notes)
3. "Back" outlined button
4. "Accept" filled button — triggers commit; disabled while request is in-flight
5. If an `ApiError` is present: `<ErrorCard>` rendered below the buttons

**Success state render:**
1. Heading: "Logged"
2. Key values: logged_at, meal_type, dish_name, kcal
3. "Log Another" outlined button

**Platform primitives used:**

| Primitive | Usage |
|---|---|
| `apiFetch` | `GET /api/food/template`, `POST /api/food/validate`, `POST /api/food/meals` |
| `isApiError` | Check all responses |
| `ErrorCard` | Render validation and commit errors |
| `Skeleton` | While template is loading on mount |

`CreateForm` is not used — the flow requires a custom two-step interaction (paste + preview + accept) that `CreateForm` does not support. `TableView` is not used — no meal list in this sprint.

**Note on `DetailView`:** The preview panel is a bespoke read-only field list, not `DetailView`, because the data is not a `Dataset` row and there is no schema or `onBack` contract to wire. Implement it as a plain `<dl>` or `<table>` styled with Atlas tokens (`--md-sys-color-surface`, `--space-md`, `body` typescale).

---

## 8. Platform Impact

None required. This slice must not introduce a new platform component. Ports already in use:
- WorkoutTracker: `8011`
- FoodTracker (this sprint): `8012`

---

## 9. Known Constraints and Decisions

### 9.1 `tools.py` is not called by the backend

`tools.py` hardcodes `host="127.0.0.1"` for its Postgres connection. Inside Docker on `atlas-net`, this resolves to the container itself, not Postgres. The backend uses `get_db()` from `database.py` (which reads `ATLAS_PG_HOST`) and issues its own SQL for the insert. The `tools.py` file and the MCPGateway registration are unchanged; both code paths write to the same table without conflict.

### 9.2 Validation occurs twice (validate + commit)

The server holds no state between the two calls. The commit endpoint re-validates for safety. This is intentional and consistent with the no-hidden-durable-state principle.

### 9.3 `confidence` scale difference

The input JSON uses `confidence` as an integer `1`–`5` (matching the database). The existing `tools.py` docstring describes the same scale. The template in §5.1 uses `4` as the example value to match this range. (An earlier draft of this document used `[0,1]` as the confidence scale; that was inconsistent with the database schema and is corrected here.)

### 9.4 `dish_name` derivation

When `items` has multiple entries, `dish_name` is derived by joining all `items[].name` values with `", "`. The preview displays the derived value so the user can verify it.

### 9.5 `kcal` precision

The database column is `NUMERIC(7,0)` (integer). The backend rounds the input value to the nearest integer before insert. The preview displays the rounded value.

---

## 10. Acceptance Criteria

- [ ] Input page is accessible via the Atlas Shell at `/food`
- [ ] "Generate Template" displays the canonical JSON template and the "Copy Template" button copies it to clipboard
- [ ] Pasting valid JSON and clicking "Log Meal" shows the preview panel with normalised values
- [ ] The preview shows the derived `dish_name` and rounded `kcal`
- [ ] Clicking "Accept" writes exactly one row to `foodtracker.food_logs` and shows the success confirmation
- [ ] Clicking "Log Another" from success returns to idle with a blank paste area
- [ ] Invalid JSON (syntax error, missing field, out-of-range value) is rejected with a structured `ErrorCard`; the paste area remains visible with the pasted content intact
- [ ] A commit error (unexpected DB failure) shows `ErrorCard` on the preview panel without clearing it
- [ ] No row is written to the database unless the user explicitly clicks "Accept"
- [ ] No draft state is persisted to the database at any point
- [ ] Backend starts cleanly from `docker compose up` at port `8012`

---

## 11. Next Slice (Preview)

FoodTracker02 — Logged Meals Review UI
