# UI Implementation Guide
> **Status:** Active — updated as implementation evolves. May change during feature work.
> **Audience:** LLMs doing frontend work. Include this file in every UI prompt.
> **Relationship:** Implements the types from `R-CON-BP-04` (UI Data Contract). Applies visual rules from `UI_DesignLanguage.md`. Does not define either.

---

## 0. Ground Rules

Before writing any UI code:

1. Types come from `R-CON-BP-04` — never redefine `Dataset`, `ColumnSchema`, or `ApiError` locally.
2. Visual decisions come from `UI_DesignLanguage.md` — never use hex values or font sizes not defined there.
3. Data fetching uses `apiFetch` from `platform-ui/api/client.ts` — never raw `fetch`.
4. Primitives are configured, not extended — never create app-specific components.
5. Invalid configs render `WarningPlaceholder` — never crash, never render blank.

---

## 1. Stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | React 18, functional components + hooks | No class components |
| Styling | CSS custom properties + scoped CSS | Tailwind for utility layout only |
| Charts | Recharts | No other chart library |
| Design language | Material 3 (constrained subset) | See `UI_DesignLanguage.md` |
| HTTP | `apiFetch` via `platform-ui/api/client.ts` | Never raw fetch |
| Backend | FastAPI + Pydantic | See `R-CON-BP-04` for models |
| Icons | Material Symbols Rounded | Font-based, variable font |

---

## 2. File Structure

The Atlas Shell is the UI host. Platform UI primitives live under `platform-ui/`.

```
02_Platform/02_Atlas_Shell/
  index.html
  package.json
  vite.config.ts
  src/
    shell/
      main.tsx          ← Entry point — register app shells here as side-effects
      Router.tsx        ← BrowserRouter routing
      ShellLayout.tsx   ← Sidebar + BottomNav + content area
      ShellContext.ts   ← Active app context
      shell.css         ← Shell layout styles (design tokens + shell chrome)
    navigation/
      Sidebar.tsx
      BottomNav.tsx
      MoreMenu.tsx
    launcher/
      AppLauncher.tsx
    registry/
      AppRegistry.ts
    hooks/
      useShell.ts
    types.ts            ← AppConfig, NavItem (shell contracts)
  platform-ui/          ← Platform UI primitives (consumed via @platform-ui alias)
    api/
      client.ts         ← apiFetch, isApiError, request log
      types.ts          ← All types from R-CON-BP-04 (single source, do not duplicate)
    components/
      TableView.tsx       ← Renders any Dataset as a sortable/filterable table
      DetailView.tsx      ← Renders a single row as a key-value card
      BarChart.tsx        ← Category comparison (grouped / stacked / 100%)
      LineChart.tsx       ← Time-based trend
      ComboChart.tsx      ← Combined bar + line on shared or dual axis
      ErrorCard.tsx       ← Renders ApiError — used by all primitives automatically
      WarningPlaceholder.tsx  ← Invalid config fallback — never crashes, never blank
      DebugPanel.tsx      ← Slide-in request log, Ctrl+Shift+D
      Skeleton.tsx        ← Loading placeholder rows
      CreateForm.tsx      ← Entity creation form
    hooks/
      useDataset.ts       ← Standard data fetching hook
    index.css             ← All design tokens + component base styles

03_Application/<AppName>/
  src/
    shellConfig.ts        ← Registers app into AppRegistry (side-effect import)
    App.tsx               ← App root component (lazy-loaded by shell)
    <Page>.tsx            ← One file per page/view
  backend/
    routers/<app>.py      ← FastAPI router returning Dataset
    platform/
      models.py           ← Dataset, ColumnSchema, DatasetMeta (import everywhere)
      errors.py           ← api_error() helper
```

**Rules:**
- New object type → new router + new page. No new components unless new primitive behaviour is needed.
- Never import between application routers. Share types via `platform/models.py` only.
- `platform-ui/api/types.ts` is the frontend mirror of `platform/models.py`. Keep them in sync.
- Import platform-ui via the `@platform-ui` alias — never via relative paths.

---

## 3. API Client

```typescript
// platform-ui/api/client.ts — do not modify during feature work

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T | ApiError> {
  const request_id = crypto.randomUUID().slice(0, 8);
  const url    = `/api${path}`;
  const method = options?.method ?? "GET";
  const start  = Date.now();

  try {
    const res  = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...options?.headers },
    });
    const data = await res.json();
    pushLog({ request_id, url, method, status: res.status, duration: Date.now() - start, response: data });
    return data;
  } catch (err) {
    const error: ApiError = {
      error: { code: "NETWORK_ERROR", message: String(err), request_id, detail: err },
    };
    pushLog({ request_id, url, method, status: 0, duration: Date.now() - start, response: error });
    return error;
  }
}

export function isApiError(x: unknown): x is ApiError {
  return typeof x === "object" && x !== null && "error" in x;
}
```

---

## 4. `useDataset` Hook

```typescript
// platform-ui/hooks/useDataset.ts

export function useDataset(path: string, params?: Record<string, string>) {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [error,   setError]   = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const query = params ? "?" + new URLSearchParams(params) : "";
    apiFetch<Dataset>(`${path}${query}`).then(res => {
      if (isApiError(res)) setError(res);
      else setDataset(res);
      setLoading(false);
    });
  }, [path, JSON.stringify(params)]);

  return { dataset, error, loading };
}
```

---

## 5. Primitives Reference

### 5.1 TableView

```tsx
<TableView
  dataset={dataset}             // null → renders Skeleton; ApiError → renders ErrorCard
  onRowClick={(row) => ...}     // navigates to DetailView
  onDelete={(id) => ...}        // rendered only if meta.row_actions includes "delete"
  onEdit={(row) => ...}         // rendered only if meta.row_actions includes "edit"
/>
```

Behaviour:
- Columns, types, labels derived from `schema[]` in declaration order.
- Sortable columns (default: all) get a sort chevron. Click cycles: asc → desc → none.
- Filterable columns get an inline text input below the header.
- `number` columns right-aligned. `date` columns formatted per `format` or ISO default.
- Pagination controls appear when `meta.total > meta.page_size`.
- Empty `rows` → empty state: icon + "No data yet".

### 5.2 DetailView

```tsx
<DetailView
  row={row}             // single Row object
  schema={schema}       // ColumnSchema[] — only fields with detail_visible: true shown
  onBack={() => ...}    // back navigation
/>
```

Read-only. No edit controls inside DetailView — editing is a separate page/dialog.

### 5.3 BarChart

```tsx
<BarChart
  dataset={dataset}
  mapping={{
    x:            "exercise",
    y:            "volume_kg",
    aggregation:  "sum",
    group_by?:    "athlete",
    bar_mode?:    "grouped",
  }}
  options={{ title: "Volume by Exercise" }}
/>
```

### 5.4 LineChart

```tsx
<LineChart
  dataset={dataset}
  mapping={{ x: "date", y: "volume_kg", aggregation: "sum" }}
  options={{ title: "Volume over Time" }}
/>
```

### 5.5 ComboChart

```tsx
<ComboChart
  dataset={dataset}
  mapping={{
    x: "date",
    series: [
      { y: "volume_kg", type: "bar",  label: "Volume",    aggregation: "sum" },
      { y: "intensity", type: "line", label: "Intensity", aggregation: "avg" },
    ]
  }}
  options={{ title: "Volume & Intensity" }}
/>
```

### 5.6 ErrorCard

```tsx
<ErrorCard error={apiError} />
// Rendered automatically by TableView, BarChart, LineChart, ComboChart on ApiError.
// Shows: error.message (prominent) + collapsible error.detail + request_id
```

### 5.7 WarningPlaceholder

```tsx
<WarningPlaceholder
  reason="bar_mode requires group_by"
  suggestion="Add group_by: 'athlete' to the mapping, or remove bar_mode"
  config={invalidMappingObject}
/>
// Never dismissible. Always explains why and suggests the fix.
```

### 5.8 CreateForm

```tsx
import CreateForm from "@platform-ui/components/CreateForm";
import type { FormField } from "@platform-ui/api/types";

const FIELDS: FormField[] = [
  { key: "title",    label: "Title",    type: "string", required: true },
  { key: "priority", label: "Priority", type: "enum",   required: true,
    options: [
      { value: "low", label: "Low" },
      { value: "medium", label: "Medium" },
      { value: "high", label: "High" },
    ]
  },
  { key: "due_date", label: "Due Date", type: "date" },
];

<CreateForm
  title="New Task"
  fields={FIELDS}
  onCancel={() => setCreating(false)}
  onSubmit={async (data) => {
    const res = await apiFetch<Dataset>("/tasks", { method: "POST", body: JSON.stringify(data) });
    if (isApiError(res)) return res;
    setDataset(res);
    setCreating(false);
  }}
/>
```

**Field type → input mapping:**

| `FormField.type` | Rendered input |
|---|---|
| `"string"` | `<input type="text">` |
| `"number"` | `<input type="number">` |
| `"date"` | `<input type="date">` |
| `"enum"` | `<select>` — `options` is required |
| `"boolean"` | `<select>` with Yes / No options |

---

## 6. DebugPanel

Toggle: `Ctrl+Shift+D`. Available in all environments.

Shows the last 50 API requests: URL, method, HTTP status, duration, response body, `request_id`.
Platform gap events from `WarningPlaceholder` appear tagged `[PLATFORM GAP]`.

---

## 7. Failure & Fallback Reference

| Situation | What renders |
|---|---|
| Endpoint returns `ApiError` | `ErrorCard` — message + collapsible detail |
| Network error / timeout | `ErrorCard` — code: `NETWORK_ERROR` |
| `dataset` is `null` (loading) | `Skeleton` — 3 animated placeholder rows |
| `rows` is empty array | Empty state — icon + "No data yet" |
| `rows` contains undeclared field | Silent ignore |
| `row` missing `id` field | `WarningPlaceholder` |
| `mapping.x` or `.y` key not in `schema` | `WarningPlaceholder` + DebugPanel log |
| `mapping.y` not `type: "number"` | `WarningPlaceholder` + DebugPanel log |
| `bar_mode` without `group_by` | `WarningPlaceholder` + DebugPanel log |
| `ComboChart` < 2 series | `WarningPlaceholder` |
| Unsupported view type | `WarningPlaceholder` tagged `[PLATFORM GAP]` |

---

## 8. Page Pattern

This is the canonical pattern for every new object type. Copy it exactly.

```tsx
// 03_Application/<App>/src/<Name>Page.tsx
import { useState } from "react";
import { useDataset } from "@platform-ui/hooks/useDataset";
import { apiFetch, isApiError } from "@platform-ui/api/client";
import TableView from "@platform-ui/components/TableView";
import DetailView from "@platform-ui/components/DetailView";
import ErrorCard from "@platform-ui/components/ErrorCard";
import type { Row } from "@platform-ui/api/types";

export default function WorkoutSessions() {
  const [page, setPage]         = useState(1);
  const [selected, setSelected] = useState<Row | null>(null);
  const { dataset, error, loading } = useDataset(
    "/workout/sessions",
    { page: String(page) }
  );

  if (error)    return <ErrorCard error={error} />;
  if (selected) return (
    <DetailView row={selected} schema={dataset!.schema} onBack={() => setSelected(null)} />
  );

  return (
    <div className="page">
      <h1>Workout Sessions</h1>
      <TableView
        dataset={loading ? null : dataset}
        onRowClick={setSelected}
        onDelete={(id) => apiFetch(`/workout/sessions/${id}`, { method: "DELETE" })}
      />
    </div>
  );
}
```

**Adding a new object type:**
1. Create `backend/routers/<name>.py` → return a `Dataset` with its schema.
2. Create `src/<Name>Page.tsx` inside the application → copy the pattern above.
3. Register the page in the application's `App.tsx` routing.
4. Done. No new components. No new types.

---

## 9. CSS Tokens and Typography

All design tokens (colors, spacing, shape, elevation, motion) and typography classes are defined in `platform-ui/index.css`.

**Canonical location:** `platform-ui/index.css` — do not redefine tokens in component files.
**Token values:** See `UI_DesignLanguage.md §3` (colors), `§4` (typography), `§5` (elevation), `§6` (shape), `§7` (spacing), `§9` (motion).

Typography classes (5 levels only — do not invent others):

| Class | Size | Weight | Usage |
|---|---|---|---|
| `.type-display`  | 28px | 400 | Page titles, large metric values |
| `.type-headline` | 22px | 400 | Card titles, section headings |
| `.type-title`    | 16px | 500 | Table column headers, dialog titles |
| `.type-body`     | 14px | 400 | Table cell content, form labels |
| `.type-label`    | 12px | 500 | Chips, badges, axis labels, metadata |

---

## 10. Application Registration (Shell Integration)

Each application registers itself into the Atlas Shell via `shellConfig.ts`:

```typescript
// 03_Application/<App>/src/shellConfig.ts
import { AppRegistry } from '@atlas/shell';
import React from 'react';

AppRegistry.register({
  appId:    'workout',
  label:    'Workout',
  basePath: '/workout',
  component: React.lazy(() => import('./App')),
  mobilePrimaryNav: [
    { id: 'log',         label: 'Log',         path: '/workout' },
    { id: 'performance', label: 'Performance', path: '/workout/performance' },
  ],
  desktopNav: [
    { id: 'log',         label: 'Log',         path: '/workout' },
    { id: 'performance', label: 'Performance', path: '/workout/performance' },
    { id: 'history',     label: 'History',     path: '/workout/history' },
  ],
});
```

Then add a side-effect import in `02_Platform/02_Atlas_Shell/src/shell/main.tsx`.

---

## 11. What Is Out of Scope

Do not build these. Raise as platform gaps via `WarningPlaceholder` if encountered.

| ❌ Out of scope | ✅ Use instead |
|---|---|
| Pie charts | `BarChart` + `bar_mode: "stacked_percent"` |
| Scatter / bubble / heatmap charts | Raise as platform gap |
| App-specific UI components | Configure `TableView` / `DetailView` via schema |
| Charts fetching their own data | Charts always receive `dataset` prop |
| Raw `fetch` calls | `apiFetch` from `@platform-ui/api/client` |
| Hardcoded hex colors | CSS custom properties from `platform-ui/index.css` |
| Font sizes not in §9 | Use closest defined level |
| FAB, Snackbar | Not in Atlas component set |
| Bottom Nav implementation | Shell-owned — declared via `AppConfig.mobilePrimaryNav` |
