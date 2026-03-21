Purpose

Deliver the first end-to-end reporting slice for FoodTracker: a Report screen in the web app with two vertically stacked column charts that visualize nutritional values over time and support the core navigation model the user wants.

This slice introduces the first intentional reporting read experience over foodtracker.food_logs, which currently supports meal logging but not analytics/reporting views .

Scope
Included

New Report route in the web app

Two vertically stacked chart panels

One metric selector per chart

Selectable metrics (display order): Protein (protein_g), Calories (kcal), Carbohydrates (carbs_g), Fat (fat_g), Fiber (fiber_g). Both charts may independently select any metric; duplicate selection across the two charts is permitted.

Default screen state:

current month

daily (non-aggregated)

top chart = protein

bottom chart = calories

Time scopes:

all time

current year

current month

current week

Drill path:

all time → year → month → week

Display modes:

aggregated

daily

Mode availability:

all time: aggregated and daily

year: aggregated and daily

month: aggregated and daily

week: daily only

Backend reporting endpoint with server-side aggregation

Frontend metric switching without refetch when the current payload already contains all supported metrics

Material 3-aligned page structure and controls

Excluded

Prefetching or background loading of non-visible report states

Client-side aggregation from a full raw-data cache

Goals, targets, or recommendations

Missing/partial meal completeness indicators

Period-over-period comparisons

Arbitrary custom date ranges

Export/share

Table-first reporting UI

Meal-level drilldown

User Flow

User opens the Report screen.

System loads the default report state only:

current month

daily mode

UI shows two vertically stacked column charts:

top chart showing Protein (g)

bottom chart showing Calories (kcal)

User changes the metric on either chart using the chart’s selector.

User switches between available scopes:

all time

year

month

week

User switches between aggregated and daily in all-time, year, and month views.

User drills down by clicking a bar column in either chart. Bar-click on any bucket triggers drill. Both charts share page-level scope, period, and mode state; clicking a bar in either chart changes both charts simultaneously. Drill is only available in aggregated mode.

year bucket from all-time

month bucket from year

week bucket from month aggregated

User navigates back using a single back button that reverts to the previous scope and period. Back-navigation is a simple stack (not a clickable breadcrumb trail). The scope selector is independent of drilled state: it always refers to the system-current period for that scope, and selecting a scope from the selector resets to the current system period and clears drilldown state.

Principles

Keep the slice fully usable, not partially demonstrative.

Default to the most useful state: current month, daily values.

Backend owns aggregation.

Load only what is needed first.

Keep metric switching cheap: no refetch if the current response already includes the metric.

Keep time navigation explicit and bounded.

Do not add optimization complexity before the reporting UX is proven.

Data Contract
Endpoint

GET /api/food/report

Request Parameters

scope: all_time | year | month | week

period_key: string identifying the selected period. Format by scope:

  scope       period_key format     example
  ---------   -------------------  -----------
  all_time    omit (not required)  —
  year        YYYY                 "2025"
  month       YYYY-MM              "2025-03"
  week        YYYY-WNN (ISO week)  "2025-W12"

mode: aggregated | daily

Response Shape

The endpoint returns a Dataset (Atlas UI Data Contract v1.0). The response is not a bespoke JSON shape.

Each bucket is a Dataset row where id = bucket_key. The schema declares one column per metric plus bucket_label. Example response for scope=month, mode=daily:

{
  "meta": {
    "object_type": "food_report_bucket",
    "label": "March 2025 — Daily",
    "total": 31,
    "page": 1,
    "page_size": 31,
    "row_actions": []
  },
  "schema": [
    { "key": "bucket_label", "label": "Date",            "type": "string",  "sortable": false },
    { "key": "kcal",         "label": "Calories (kcal)", "type": "number" },
    { "key": "protein_g",    "label": "Protein (g)",     "type": "number" },
    { "key": "carbs_g",      "label": "Carbs (g)",       "type": "number" },
    { "key": "fat_g",        "label": "Fat (g)",         "type": "number" },
    { "key": "fiber_g",      "label": "Fiber (g)",       "type": "number" }
  ],
  "rows": [
    {
      "id": "2025-03-01",
      "bucket_label": "1",
      "kcal": 0,
      "protein_g": 0,
      "carbs_g": 0,
      "fat_g": 0,
      "fiber_g": 0
    }
  ]
}

Chart Mapping

Each chart panel declares a BarChartMapping over the Dataset. The mapping is local frontend state — it is not returned by the backend:

{
  "x": "bucket_label",
  "y": "<user-selected metric key>",
  "aggregation": "sum"
}

The selected metric key is one of: kcal, protein_g, carbs_g, fat_g, fiber_g. The user's per-chart selection determines which y key is active. The Dataset always contains all five metric columns, so metric switching requires no backend call.

Errors must use the ApiError envelope (UI Data Contract v1.0).

Supported Metrics in Payload

Use existing nutrition fields already stored on foodtracker.food_logs, including at minimum:

kcal

protein_g

carbs_g

fat_g

fiber_g

These fields exist in the current schema and can be aggregated directly from stored meal rows .

Bucket Rules

all_time + aggregated → year

all_time + daily → day

year + aggregated → month

year + daily → day

month + aggregated → week

month + daily → day

week → day only

Notes

The response must include all supported metrics for each bucket, even though each chart displays only one selected metric at a time.

This allows metric changes within the current view without another backend call.

Bucket generation must include zero-value buckets where needed so the x-axis remains complete and stable.

System Behavior
Default State

On first load, the report page must request and render:

scope = month

period_key = current month

mode = daily

Frontend defaults:

top chart metric = protein_g

bottom chart metric = kcal

Aggregation Ownership

Aggregation happens on the backend.

The frontend does not compute report aggregations from raw meal rows in this slice.

Fetching Behavior

Initial load:

fetch only the default state

Subsequent changes:

metric change within current payload → no backend call

scope change → backend call

mode change → backend call

drilldown to a different period → backend call

breadcrumb/back navigation to a different period/scope → backend call unless already retained in local page state

Drill Behavior

all time aggregated: selecting a year bucket opens that year

year aggregated: selecting a month bucket opens that month

month aggregated: selecting a week bucket opens that week

week is the deepest scope in this slice

Daily vs Aggregated

Daily mode shows one bucket per calendar day in the selected period

Aggregated mode shows grouped buckets appropriate to the selected scope

Time Grouping

Use server time for this slice

Use calendar-aligned periods for year, month, and week

Weekly scope is current week when directly selected from scope controls

Chart Behavior

Two vertically stacked column charts

Same x-axis buckets for both charts in the current view

Independent metric selector per chart

Independent y-axis scaling per chart

Material 3 styling applies to page layout, cards, selectors, and control hierarchy; no special chart-library decision is part of this slice

Architecture Impact
Backend

Adds the first reporting read endpoint over foodtracker.food_logs

Adds aggregation and bucket-generation logic for:

all-time

year

month

week

Adds support for both aggregated and daily response modes

No schema changes

No migrations

Frontend

Adds a new Report route/page at /food/report

Shell navigation: shellConfig.ts adds a Report NavItem to mobilePrimaryNav and desktopNav:

  { id: 'report', label: 'Report', path: '/food/report', order: 2 }

secondaryMenu is unchanged (remains empty). After this change mobilePrimaryNav and desktopNav each contain two entries: Log (order 1) and Report (order 2).

Adds two chart instances on one screen

Adds independent metric selectors

Adds scope control and mode control

Adds drill/navigation state (back button; scope selector always system-relative)

Mode selector is hidden when only one mode is valid (week scope, daily-only)

Leaves the existing intake/validate/commit flow unchanged

Performance/Delivery Posture

This slice intentionally does not include prefetching or background hydration of alternate scopes/modes.

Optimization is deferred until the report is working end to end.

Constraints

Must use the existing foodtracker.food_logs table only

Must remain read-only

Must not introduce new persistence, caching infrastructure, or background jobs

Must not require user-defined date ranges

Must not require a backend call when only switching metrics within the already loaded dataset

Must support week view; omitting it would be incorrect for this slice

Must ship with the locked default state:

current month

daily

protein top

calories bottom

Acceptance Criteria
Product

User can open a new Report screen in the web app.

The page shows two vertically stacked column charts.

The default state is:

current month

daily mode

protein on top

calories on bottom

User can independently change the metric shown in each chart.

User can switch between:

all time

current year

current month

current week

User can switch between aggregated and daily in all-time, year, and month views.

Week view is daily only.

User can drill:

all time → year

year → month

month → week

User can navigate back up the hierarchy.

Data/Behavior

Backend returns chart-ready buckets for the selected scope/mode/period.

Each bucket contains all supported metrics needed for chart switching.

Daily views include zero-value buckets for dates with no entries in the selected period.

Metric changes inside the current loaded view do not trigger a new backend call.

Scope, mode, and drill changes do trigger a backend call.

Existing meal logging behavior is unchanged.

Delivery Boundaries

No schema migration is required.

No prefetch/background loading is required.

No client-side aggregation from raw rows is required.

Open Questions

None. All blocking questions identified in the spec readiness review have been resolved in this document.

Out of Scope

Background prefetch of alternate report states

Smart local caching strategy beyond normal page state retention

Missing/partial-day highlighting

Comparison overlays

Goal lines or thresholds

Exporting

User-local timezone handling

Mobile-specific refinements

Advanced chart interactivity beyond metric selection and drill navigation