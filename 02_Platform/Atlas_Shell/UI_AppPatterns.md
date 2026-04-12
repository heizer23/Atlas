# UI App Patterns
> **Status:** Active — updated when a new canonical pattern is established or a violation is corrected.
> **Audience:** LLMs doing UI work, humans reviewing visual consistency.
> **Relationship:** Applies the rules from `UI_DesignLanguage.md`. Shows how those rules materialise in application code. Cross-references actual files — check git blame if an entry seems stale.

The purpose of this document is to answer the question: *"For this type of element, what does correct Atlas code look like, and where can I see it?"*

---

## How to use this document

Each section covers one UI pattern. It provides:
- **Canonical form** — the CSS classes or tokens to use
- **Reference** — a file that does it correctly (as of the date noted)
- **Known violations** — files that deviate and must be fixed before/during their next sprint

If you are implementing a new page, copy from a Reference, not from a violation file.

---

## 1. Page structure

Every application page follows the same shell:

```tsx
<div className="page">
  <div className="page-header">
    <h1 className="type-headline">Page Title</h1>
    <div className="page-toolbar">
      {/* primary action button lives here */}
    </div>
  </div>
  {/* content */}
</div>
```

**Rules:**
- `h1` always uses `.type-headline` (22px, Display font).
- Page padding comes from `.page` — do not add `padding` via inline style on the wrapper `div`.
- Do not use `maxWidth` on the page wrapper. Width is controlled by the shell layout.

**Reference:** `03_Application/FoodTracker/src/EntriesPage.tsx`
**Known violations:** `03_Application/NumericSeries/src/SeriesListPage.tsx`, `03_Application/NumericSeries/src/SeriesDetailPage.tsx` — both use `padding: '1rem'` and `maxWidth` inline styles instead of `.page`.

---

## 2. Buttons

Four button variants exist. Use them as a strict hierarchy — do not invent a fifth.

| Variant | Class | Token used | When |
|---|---|---|---|
| Primary action | `.btn-filled` | `primary` | One per toolbar or form. Create, Save, Confirm. |
| Secondary action | `.btn-outlined` | `outline` | Cancel, Back, secondary navigation. |
| Inline text action | `.btn-text` | `primary` | Low-emphasis actions inside a row or card. |
| Destructive action | `.btn-danger` | `error` | Delete. Always requires a confirmation dialog. |
| Icon-only action | `.icon-btn` | `on-surface-variant` | Icon buttons in table rows (edit, delete icons). |

**Shape:** All buttons use `border-radius: var(--radius-button)` (20px). Never use `4px`, `6px`, or `3px` on a button.

**Toolbar "add" button:** Use `.btn-filled` with a leading `+` character or a Material Symbol icon. Do not use an oversized `+` with custom font-size and custom padding.

```tsx
// Correct — toolbar primary action
<button className="btn-filled" onClick={() => navigate('/series/new')}>
  + New series
</button>

// Correct — destructive action (with dialog guard)
<button className="btn-danger" onClick={handleDeleteSeries}>
  Delete series
</button>
```

**Reference:** `03_Application/FoodTracker/src/EntriesPage.tsx` (DeleteConfirmDialog + action buttons)
**Known violations:**
- `03_Application/NumericSeries/src/SeriesListPage.tsx` — `+` button uses `borderRadius: '6px'` and hardcoded `background: 'var(--md-sys-color-primary, #7c6af5)'` (fallback hex is wrong color)
- `03_Application/NumericSeries/src/SeriesDetailPage.tsx` — delete series button uses `background: '#8b2020'`; row delete uses `background: '#5a1010'`. Both must use `.btn-danger`.

---

## 3. Tables

The platform provides `TableView`. Use it. Do not write `<table>` markup in application pages.

```tsx
import TableView from '@platform-ui/components/TableView';

<TableView
  dataset={loading ? null : dataset}
  onRowClick={setSelected}
  onDelete={(id) => apiFetch(`/series/${id}`, { method: 'DELETE' })}
/>
```

`TableView` handles: column headers from schema, sort, filter, pagination, empty state, skeleton loading, error card, row delete icon button.

**When a custom list layout is required** (e.g. cards with sparklines that the schema-driven TableView cannot produce): use the same surface and border tokens as TableView uses internally.

```tsx
// Correct custom list row
<div
  style={{
    background: 'var(--md-sys-color-surface)',
    border: '1px solid var(--md-sys-color-outline-variant)',
    borderRadius: 'var(--radius-card)',
    padding: 'var(--space-sm) var(--space-md)',
  }}
>
```

**Known violations:** `03_Application/NumericSeries/src/SeriesDetailPage.tsx` — custom `<table>` with hardcoded `#2e2e3e`, `#1e1e2e`, `#a0a0b0`, `#888`. Replace with `TableView` or, if the custom layout is genuinely required, use only token references.

---

## 4. Input fields

All inputs use the same visual treatment regardless of the form they appear in.

```tsx
// Correct input
<input
  type="text"
  style={{
    background: 'var(--md-sys-color-surface)',
    border: '1px solid var(--md-sys-color-outline-variant)',
    borderRadius: 'var(--radius-input)',
    color: 'var(--md-sys-color-on-surface)',
    padding: 'var(--space-sm) var(--space-md)',
  }}
/>

// Focused border — use outline token
// :focus { border-color: var(--md-sys-color-outline); outline: 2px solid var(--md-sys-color-primary); }
```

Date pickers (`type="date"`, `type="datetime-local"`) use the same tokens as text inputs. They are not special-cased.

**Background is always `--md-sys-color-surface` (light, `#F8FAFE`).** Never use a dark background color on an input. Atlas is a light-only theme.

**Reference:** `03_Application/NumericSeries/src/SeriesDetailPage.tsx` lines 187–195 (creation mode form — correct)
**Known violations:** `03_Application/NumericSeries/src/SeriesDetailPage.tsx` lines 243–250, 293–299 (detail mode add/edit forms) — use `background: '#121220'` (dark theme color). These are in the same file as the correct example.

---

## 5. Forms — CreateForm vs inline

**Use `CreateForm`** for any entity-creation flow that fits the field-list model (text, number, date, enum, boolean inputs). It handles layout, validation display, submit/cancel actions, and error handling.

```tsx
import CreateForm from '@platform-ui/components/CreateForm';
import type { FormField } from '@platform-ui/api/types';

const FIELDS: FormField[] = [
  { key: 'label_name', label: 'Series name', type: 'string', required: true },
];

<CreateForm
  title="New Series"
  fields={FIELDS}
  onCancel={() => navigate('/series')}
  onSubmit={async (data) => { ... }}
/>
```

**Use an inline form** only when the interaction is tightly coupled to a table row (e.g. inline edit of a single row). Even then, use token-based styles on the inputs (see §4).

**Known violations:** `03_Application/NumericSeries/src/SeriesDetailPage.tsx` — creation mode uses a handwritten form instead of `CreateForm`.

---

## 6. Confirmation dialogs (destructive actions)

Destructive actions (`btn-danger`) must show a confirmation dialog before executing. Use `browser.confirm()` only as a temporary scaffold — prefer an explicit dialog component.

Canonical dialog structure (until a shared `ConfirmDialog` primitive exists):

```tsx
<div role="dialog" aria-modal="true" style={{ position: 'fixed', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)', zIndex: 1000 }}>
  <div style={{ background: 'var(--md-sys-color-surface)', borderRadius: 'var(--radius-dialog)', padding: 'var(--space-lg)', maxWidth: '360px', width: '90%', boxShadow: 'var(--elevation-2)' }}>
    <h2 className="type-title">Delete this series?</h2>
    <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: 'var(--space-sm) 0 var(--space-md)' }}>
      All measurements will be permanently removed.
    </p>
    <div style={{ display: 'flex', gap: 'var(--space-sm)', justifyContent: 'flex-end' }}>
      <button className="btn-outlined" onClick={onCancel}>Cancel</button>
      <button className="btn-danger" onClick={onConfirm}>Delete</button>
    </div>
  </div>
</div>
```

**Reference:** `03_Application/FoodTracker/src/EntriesPage.tsx` — `DeleteConfirmDialog`
**Known violations:** `03_Application/NumericSeries/src/SeriesDetailPage.tsx` — uses `window.confirm()` for series deletion; no dialog for row deletion.

---

## 7. Inline sparklines and mini-charts

Sparklines that appear inside list rows or cards use Recharts `LineChart` + `ResponsiveContainer`. The line color must come from the chart palette, not from an arbitrary purple.

```tsx
<Line
  type="monotone"
  dataKey="v"
  dot={false}
  stroke="var(--atlas-chart-1)"   // ← always a chart token
  strokeWidth={1.5}
  isAnimationActive={false}
/>
```

Chart tokens (`--atlas-chart-1` through `--atlas-chart-4`, `--atlas-chart-line-1`, `--atlas-chart-line-2`) are defined in `platform-ui/index.css`. Assign in order. First series is always `--atlas-chart-1`.

**Known violations:** `03_Application/NumericSeries/src/SeriesListPage.tsx` line 44 — `stroke="#7c6af5"` (hardcoded purple, not a chart token).

---

## 8. Status / state badges

State labels displayed inside a list row or table cell use a chip-style badge. Use tertiary or error tokens for semantic meaning — never hardcoded hex.

| Semantic | Background token | Text token |
|---|---|---|
| Neutral / default | `--md-sys-color-surface-variant` | `--md-sys-color-on-surface-variant` |
| Active / selected | `--md-sys-color-primary-container` | `--md-sys-color-on-primary-container` |
| Warning | `--md-sys-color-tertiary-container` | `--md-sys-color-tertiary` |
| Error / critical | `--md-sys-color-error-container` | `--md-sys-color-error` |

```tsx
// Example: "low stock" badge
<span style={{
  background: 'var(--md-sys-color-tertiary-container)',
  color: 'var(--md-sys-color-tertiary)',
  borderRadius: 'var(--radius-button)',
  padding: '2px var(--space-sm)',
  fontSize: '12px',
  fontWeight: 500,
}}>
  low stock
</span>
```

**Known violations:** `03_Application/StorageTracker/src/` — `StateBadge` uses hardcoded `#888` and `#b45309`.

---

## 9. Secondary / metadata text

Text that communicates metadata (IDs, timestamps, secondary labels) uses `--md-sys-color-on-surface-variant`. Never use `#888`, `#a0a0b0`, or any hardcoded gray.

```tsx
<span style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
  Series ID: {label_id}
</span>
```

**Known violations:** `03_Application/NumericSeries/src/SeriesDetailPage.tsx` line 218 — `color: '#888'`; line 310 — `color: '#a0a0b0'`.

---

## 10. Deviation log

Record here when a deviation from a canonical pattern is deliberately accepted (with sprint and reason). This is not for violations that must be fixed — those are listed in §1–9 above.

| Sprint | App | Element | Deviation | Reason |
|---|---|---|---|---|
| NumericSeries/Sprint01 | NumericSeries | List layout | Custom card grid instead of TableView | Sparkline column cannot be expressed in Dataset schema |

---

## Maintenance

- When a violation is fixed (e.g. during a sprint), remove or update the "Known violations" entry in the relevant section.
- When a new element type is added to `platform-ui/index.css`, add a section here.
- When a deliberate deviation is accepted, add it to the deviation log (§10), not the violations list.
- Do not document patterns that are already fully covered by `UI_Implementation.md §5` (primitives reference) and `UI_DesignLanguage.md §10` (component map) — this document supplements those, it does not replace them.
