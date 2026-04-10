# UI Data Contract

> **Version:** v0.4
> **Authority:** R-CON-BP-04 (`.claude/rules/R-CON-BP.md`)
> **Audience:** LLMs writing backend endpoints, LLMs writing frontend components, humans reviewing API design.

Application code couples to this document, not to UI implementation details.
The Dataset contract is **stable**. The UI implementation is not.

---

## 1. Core Types

Authoritative type definitions live in two implementation files. Import from them — never redefine locally.

| File | Language |
|---|---|
| `02_Platform/Atlas_Shell/platform-ui/api/types.ts` | TypeScript |
| `02_Platform/packages/platform_contracts/contracts.py` | Python |

### 1.1 Scalar types

| Type | Valid values | Open/Closed | Notes |
|---|---|---|---|
| `ColumnType` | `"string"`, `"number"`, `"date"`, `"boolean"`, `"enum"` | Closed | Field display type |
| `RowAction` | any string | **Open** | Backend declares which actions apply. Frontend renders only what is declared. Conventional values: `"delete"`, `"edit"`, `"copy"` |
| `Aggregation` | `"sum"`, `"avg"`, `"count"`, `"max"`, `"min"` | Closed | Chart aggregation function |
| `BarMode` | `"grouped"`, `"stacked"`, `"stacked_percent"` | Closed | Bar chart stacking mode |
| `SeriesType` | `"bar"`, `"line"` | Closed | Combo chart series type |
| `YAxis` | `"left"`, `"right"` | Closed | Dual-axis binding |

### 1.2 Structures

| Structure | Key fields |
|---|---|
| `ColumnSchema` | `key`, `label`, `type`, `sortable?`, `filterable?`, `detail_visible?`, `format?` |
| `DatasetMeta` | `object_type`, `label`, `total`, `page`, `page_size`, `row_actions` |
| `Dataset` | `meta`, `schema`, `rows` |
| `Row` | `id: string` + additional fields matching schema keys |
| `ApiError` | `error.{code, message, detail?, request_id}` |
| `FormField` | `key`, `label`, `type`, `required?`, `options?`, `placeholder?`, `initialValue?` |

---

## 2. Dataset Rules

These rules are enforced by the frontend. Violations produce `WarningPlaceholder` or silent ignores as specified.

| Rule | Enforcement |
|---|---|
| Every `row` must have an `id` field (string) | `WarningPlaceholder` if missing |
| `schema` key order defines column display order | Enforced by render order |
| `row` fields not declared in `schema` are ignored | Silent — no warning, no crash |
| `row_actions` is declared by backend, not hardcoded in frontend | Frontend renders only what backend declares |
| `schema[].key` must match `row` field keys exactly (case-sensitive) | Mismatched keys render empty cells |
| `total` reflects full unpaginated count, not current page count | Used for pagination controls |

---

## 3. Chart Mapping Types

Charts are **views over a Dataset** — they never fetch their own data. A chart is a `dataset` prop plus a `mapping` that declares how to interpret it.

### 3.1 BarChartMapping

```typescript
interface BarChartMapping {
  x:           string;      // schema key — category axis
  y:           string;      // schema key — must be type: "number"
  aggregation: Aggregation;
  group_by?:   string;      // schema key — creates one series per unique value
  bar_mode?:   BarMode;     // default: "grouped" when group_by is present
}
```

| `bar_mode` | Behaviour |
|---|---|
| `"grouped"` | Bars side-by-side per category. Default when `group_by` is set. |
| `"stacked"` | Bars stacked — shows absolute totals per category. |
| `"stacked_percent"` | Bars stacked and normalized to 100% — shows composition/share. |

### 3.2 LineChartMapping

```typescript
interface LineChartMapping {
  x:           string;      // schema key — time axis preferred (type: "date")
  y:           string;      // schema key — must be type: "number"
  aggregation: Aggregation;
}
```

### 3.3 ComboChartMapping

```typescript
interface SeriesMapping {
  y:           string;      // schema key — must be type: "number"
  type:        SeriesType;  // "bar" | "line"
  label?:      string;      // legend label — defaults to schema[y].label
  aggregation: Aggregation;
  y_axis?:     YAxis;       // "left" | "right" — default: "left"
}

interface ComboChartMapping {
  x:      string;           // schema key — shared category/time axis
  series: SeriesMapping[];  // min 2 — must include ≥1 "bar" and ≥1 "line"
}
```

### 3.4 Chart Decision Tree

```
One category, one metric          →  BarChart
One category, multiple metrics    →  BarChart  +  group_by  +  bar_mode: "grouped"
Composition / share               →  BarChart  +  group_by  +  bar_mode: "stacked_percent"
Absolute stacked totals           →  BarChart  +  group_by  +  bar_mode: "stacked"
Time trend, one metric            →  LineChart
Time trend + categorical metric   →  ComboChart  (bar + line, shared axis)
Two metrics, different scales     →  ComboChart  +  y_axis: "left" / "right"
```

---

## 4. Validation Rules

If a primitive receives an invalid configuration it must render `WarningPlaceholder` and log to DebugPanel. It must never crash, render blank, or silently degrade.

| Violation | Response |
|---|---|
| `mapping.x` key not in `schema` | `WarningPlaceholder` — "key '{x}' not found in schema" |
| `mapping.y` key not in `schema` | `WarningPlaceholder` — "key '{y}' not found in schema" |
| `mapping.y` field not `type: "number"` | `WarningPlaceholder` — "y-axis field must be type: number" |
| `bar_mode` set without `group_by` | `WarningPlaceholder` — "`bar_mode` requires `group_by`" |
| `ComboChart` with fewer than 2 series | `WarningPlaceholder` — suggest `BarChart` or `LineChart` |
| `ComboChart` missing a `"bar"` series | `WarningPlaceholder` — "ComboChart requires ≥1 bar series" |
| `ComboChart` missing a `"line"` series | `WarningPlaceholder` — "ComboChart requires ≥1 line series" |
| `y_axis: "right"` with no `"left"` series | `WarningPlaceholder` — "dual axis requires ≥1 series on left" |
| `row` missing `id` field | `WarningPlaceholder` — "rows must have an id field" |
| Unsupported view type requested | `WarningPlaceholder` — "unsupported view: {type}; use BarChart, LineChart, ComboChart, TableView, or DetailView" |

---

## 5. Error Envelope

All API errors must use this shape. The frontend checks for the `error` key first on every response.

```typescript
// Successful response
{ meta: {...}, schema: [...], rows: [...] }

// Error response — always this shape, never a different error format
{
  "error": {
    "code": "INVALID_FILTER",
    "message": "Filter field 'exercis' does not exist in schema",
    "detail": { "field": "exercis", "available": ["exercise", "date", "sets"] },
    "request_id": "req_8f2a1c"
  }
}
```

**Backend FastAPI error helper:**

```python
# backend/platform/errors.py
from fastapi.responses import JSONResponse
import uuid

def api_error(code: str, message: str, detail=None, status: int = 400):
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "detail": detail,
                "request_id": uuid.uuid4().hex[:8],
            }
        }
    )
```

---

## 6. Canonical Endpoint Example

```python
# backend/routers/workout.py
from platform.models import Dataset, DatasetMeta, ColumnSchema

@router.get("/workout/sessions")
def list_sessions(page: int = 1, page_size: int = 25) -> Dataset:
    rows, total = db.get_sessions(page=page, page_size=page_size)
    return Dataset(
        meta=DatasetMeta(
            object_type="workout_session",
            label="Workout Sessions",
            total=total,
            page=page,
            page_size=page_size,
            row_actions=["edit", "delete"],
        ),
        schema_=[
            ColumnSchema(key="date",      label="Date",        type="date",   sortable=True),
            ColumnSchema(key="exercise",  label="Exercise",    type="string", filterable=True),
            ColumnSchema(key="volume_kg", label="Volume (kg)", type="number", format="kg"),
            ColumnSchema(key="notes",     label="Notes",       type="string", sortable=False),
        ],
        rows=rows,
    )
```

---

## 7. CreateForm Types

`CreateForm` is a platform primitive for creating new entities. Its field definitions reuse `ColumnType` so the backend schema vocabulary and the form vocabulary stay aligned.

```typescript
// Defined in platform-ui/api/types.ts — alongside the Dataset types

interface FormFieldOption {
  value: string;
  label: string;
}

interface FormField {
  key:           string;
  label:         string;
  type:          ColumnType;          // same vocabulary as ColumnSchema.type
  required?:     boolean;             // default: false
  options?:      FormFieldOption[];   // required when type is "enum"
  placeholder?:  string;
  initialValue?: string;              // pre-fills the field; used for edit forms
}
```

The backend does not emit `FormField` definitions — form fields are declared by the application frontend. The backend only validates the resulting POST/PATCH body and returns `Dataset | ApiError`.

---

## 8. Out of Scope

The frontend renders none of the following. If an Application requests them, `WarningPlaceholder` is rendered and the event is logged as a platform gap.

| Not supported | Use instead |
|---|---|
| Pie charts | `BarChart` + `bar_mode: "stacked_percent"` |
| Scatter / bubble charts | Not available — raise as platform gap |
| App-specific chart types | Not available — raise as platform gap |
| Charts that fetch their own data | Charts always receive `dataset` prop |
| Custom table layouts per app | Configure `TableView` via `schema` |
| Raw `fetch` in components | `apiFetch` from `platform-ui/api/client.ts` only |

---

## 9. Endpoint Categories and Dataset Obligation

**Read endpoints (GET)** that return UI-visible data must return `Dataset`. This is the core obligation of R-CON-BP-04.

**Mutation endpoints (POST, PUT, PATCH, DELETE)** are exempt from returning `Dataset`. They must:
- Return an appropriate success status (`200`, `201`, `204`).
- Return `ApiError` on failure — never a bespoke error shape.
- If a body is returned on success, it must be a typed record (not an ad-hoc untyped shape).
- A mutation that returns `Dataset` as its success body (e.g., set-and-return-all) is valid.

The distinction: if the frontend uses the response to render a data view → `Dataset` required. If the frontend uses it only to confirm success or display an error → exempt.

---

## 10. Contract Boundaries

Producers must not:
- couple payload shape to specific React components
- require frontend knowledge of backend-local model names
- invent app-local response shapes when Dataset fits (read endpoints)
- return ad hoc error formats

Consumers must not:
- assume undeclared row fields are stable
- hardcode actions that are not declared in `row_actions`
- reinterpret schema keys or change their meaning locally

---

## 11. Versioning

Current version: **v0.4**

Changes from v0.3:
- Added §9 (Endpoint Categories and Dataset Obligation): mutation endpoints (POST, PUT, PATCH, DELETE) are explicitly exempt from the Dataset requirement. Rule clarification, not a breaking change — existing read endpoints are unaffected.
- Renumbered former §9 (Contract Boundaries) to §10.
- Corrected authority path to `.claude/rules/R-CON-BP.md`.

Changes from v0.2:
- Added `initialValue?: string` to `FormField` (non-breaking additive change).

Changes from v0.1:
- Added `FormField` and `FormFieldOption` types (`CreateForm` primitive).

Changes from original R-CON-BP-04:
- Added chart mapping types (`BarChartMapping`, `LineChartMapping`, `ComboChartMapping`) and decision tree.
- Added full validation rules table.
- Updated implementation file path to `02_Platform/Atlas_Shell/platform-ui/`.

Changes to this document require:
1. An explicit decision — not a side effect of feature work.
2. Version bump in this header.
3. Corresponding update to affected producers and consumers.
4. Update to the stability requirement in R-CON-BP-04 if the contract changes classification.

Additive changes (new optional fields) are non-breaking. Removals or renames are breaking and require migration notes.
