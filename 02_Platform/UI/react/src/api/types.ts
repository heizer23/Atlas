// src/api/types.ts — single source of truth for frontend types
// Mirrors 00_Blueprint/UI/01_UI_Contract. Do not extend or override locally.
// Change this file only when the contract changes, then version-bump the contract.

export type ColumnType  = "string" | "number" | "date" | "boolean" | "enum";
export type Aggregation = "sum" | "avg" | "count" | "max" | "min";
export type BarMode     = "grouped" | "stacked" | "stacked_percent";
export type SeriesType  = "bar" | "line";
export type YAxis       = "left" | "right";
export type RowAction   = "delete" | "edit" | "copy";

export interface ColumnSchema {
  key:             string;   // matches row field key exactly — case-sensitive
  label:           string;   // human-readable column header
  type:            ColumnType;
  sortable?:       boolean;  // default: true
  filterable?:     boolean;  // default: false
  detail_visible?: boolean;  // shown in DetailView, default: true
  format?:         string;   // display hint: "€#,##0" | "kg" | "YYYY-MM-DD" | "%"
}

export interface DatasetMeta {
  object_type: string;       // e.g. "task" — snake_case, stable identifier
  label:       string;       // e.g. "Tasks" — human-readable, used in UI headings
  total:       number;       // total rows across all pages
  page:        number;       // current page, 1-indexed
  page_size:   number;       // rows per page
  row_actions: RowAction[];  // backend declares which actions are valid for this object
}

export type Row = { id: string } & Record<string, unknown>;

export interface Dataset {
  meta:   DatasetMeta;
  schema: ColumnSchema[];    // ordered — column display order matches array order
  rows:   Row[];
}

// Every API response is Dataset | ApiError. Nothing else.
export interface ApiError {
  error: {
    code:       string;      // machine-readable: "INVALID_FILTER" | "NOT_FOUND" | "NETWORK_ERROR"
    message:    string;      // human-readable — shown directly in ErrorCard
    detail?:    unknown;     // developer context — shown in DebugPanel, not in main UI
    request_id: string;      // correlates with backend log entry
  };
}

// ── CreateForm types ──────────────────────────────────────────────────────────
// Used to configure the CreateForm primitive. Field types reuse ColumnType for
// consistency — the backend schema and the form share the same type vocabulary.

export interface FormFieldOption {
  value: string;
  label: string;
}

export interface FormField {
  key:           string;
  label:         string;
  type:          ColumnType;          // "string" | "number" | "date" | "boolean" | "enum"
  required?:     boolean;             // default: false
  options?:      FormFieldOption[];   // required when type is "enum"
  placeholder?:  string;
  initialValue?: string;              // pre-fills the field; used for edit forms
}

// ── Chart mapping types ───────────────────────────────────────────────────────

export interface BarChartMapping {
  x:           string;      // schema key — category axis
  y:           string;      // schema key — must be type: "number"
  aggregation: Aggregation;
  group_by?:   string;      // schema key — creates one series per unique value
  bar_mode?:   BarMode;     // default: "grouped" when group_by is present
}

export interface LineChartMapping {
  x:           string;      // schema key — time axis preferred (type: "date")
  y:           string;      // schema key — must be type: "number"
  aggregation: Aggregation;
}

export interface SeriesMapping {
  y:           string;      // schema key — must be type: "number"
  type:        SeriesType;  // "bar" | "line"
  label?:      string;      // legend label — defaults to schema[y].label
  aggregation: Aggregation;
  y_axis?:     YAxis;       // "left" | "right" — default: "left"
}

export interface ComboChartMapping {
  x:      string;           // schema key — shared category/time axis
  series: SeriesMapping[];  // min 2 — must include ≥1 "bar" and ≥1 "line"
}
