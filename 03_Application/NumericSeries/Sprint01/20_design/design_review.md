# Design Review — numeric_series

## Verdict
- Status: APPROVED_WITH_CHANGES
- Summary: The design is well-structured, correctly classified as Application, and implementable for most surfaces. Two issues require resolution before implementation: the `sparkline_values` field in the list Dataset violates the UI Data Contract's ColumnType vocabulary, and the label_name retrieval path for batch_read on unknown series (not in `numeric_series.series`) is underspecified. Both are bounded corrections that do not require redesign of the overall architecture.

## Confirmed Problems

1. **sparkline_values in Dataset rows violates UI Data Contract ColumnType**
   - Severity: Major
   - Location: `20_design/architecture.json` → `interfaces.exposed_surfaces[GET /api/series]` and `internal_flow[step 3]`
   - Why it is a problem: The list Dataset row is described as `{id, label_name, latest_value, sparkline_values}`. `sparkline_values` is a list of floats. R-CON-BP-04 defines `ColumnType` as a closed set: `"string"`, `"number"`, `"date"`, `"boolean"`, `"enum"`. No array type exists. If the UI consumes this via the standard Dataset/TableView contract, `sparkline_values` either renders as an empty cell or triggers a `WarningPlaceholder`. The sparkline requires a non-Dataset rendering path.
   - Impact: The list view Dataset is not renderable by the standard platform UI primitives without custom frontend handling that bypasses the Dataset contract. The implementer will have to deviate from the contract and may not know this without the correction.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the Dataset contract was applied to the list surface without verifying that all row fields are expressible as valid ColumnTypes.

2. **batch_read label_name source is undefined for label_ids not in numeric_series.series**
   - Severity: Major
   - Location: `20_design/architecture.json` → `internal_flow[step 6]` and `interfaces.exposed_surfaces[POST /api/batch/series]`
   - Why it is a problem: Step 6 states "if series record doesn't exist, return empty measurements array." It also states "Joins labels.labels for name." But if a label_id is not in `numeric_series.series`, there is no join path to `labels.labels` via `numeric_series.series`. The implementer must either: (a) query `labels.labels` directly for all requested label_ids regardless of series existence, or (b) omit label_name for unknown label_ids. The design does not specify which path. The `BatchSeriesEntry` model in scaffolding requires `label_name: str` (non-optional), making option (b) a type error.
   - Impact: Implementer cannot write correct batch_read logic without guessing. The invariant "Batch read returns a result entry for every requested label_id, including empty series" requires a label_name for every entry, which requires querying `labels.labels` unconditionally.
   - Likely Cause (Design Phase): Incomplete Contract Thinking — the join path was described for the happy path only, without tracing the full data path for the declared invariant.

## Recommended Improvements

1. **Clarify list view sparkline rendering approach**
   - Location: `20_design/architecture.json` → `interfaces.exposed_surfaces[GET /api/series]`
   - Improvement: The list Dataset should carry sparkline_values as a JSON-encoded string column (type: "string") that the frontend parses and renders with a custom cell renderer, OR the sparkline data should be returned as a separate parallel API call. The architecture.json should state explicitly which approach is taken and note that this field is not rendered by standard platform TableView.
   - Why: Without this, the UI Implementer cannot determine whether to use a standard Dataset table or build a custom list component.

2. **Specify non-atomic creation recovery path**
   - Location: `20_design/architecture.json` → `risks[0]`
   - Improvement: State that if LabelEngine label creation succeeds but series insert fails, the retry path is: call POST /api/labels again — LabelEngine will return a duplicate-name error with the existing label_id — then attempt the series insert with that label_id. Add this recovery flow to `internal_flow[step 1]`.
   - Why: The risk is identified but the mitigation is not actionable. "Detect duplicate-name error" is not enough — the implementer needs to know the expected LabelEngine error code and the next step.

## Scaffold-Only Observations

1. **SeriesCreatedResponse model missing from models.py**
   - Location: `20_design/scaffolding.json` → `files[backend/models.py]`
   - Observation: The exposed surface for `POST /api/series` documents a 201 response `{label_id, label_name}`. `SeriesRecord` in models.py has these same fields, but it is not named as the creation response type. The scaffolding should either rename `SeriesRecord` to `SeriesCreatedResponse` or add an alias comment so the router author maps it correctly.
   - Impact on implementation: Minor — implementer will figure it out, but the mapping is implicit and could cause confusion.

2. **frontend/src directory lacks an index/router entry point file**
   - Location: `20_design/scaffolding.json` → `directories` and `files`
   - Observation: Only `SeriesListPage.tsx` and `SeriesDetailPage.tsx` are scaffolded for the frontend. Other applications (TaskTracker, Chronicle) include a frontend router or index entry point. No `App.tsx` or `Router.tsx` stub is listed.
   - Impact on implementation: UI Implementer will need to create the router/entry file without a stub; this is a minor gap in scaffolding completeness.

## Hard Rule Violations

1. **R-CON-BP-04 — ColumnType closed set violation**
   - Rule Source: `.claude/rules/R-CON-BP-04_ui_data_contract.md` §1.1
   - Location: `20_design/architecture.json` → `internal_flow[step 3]` output `{id=label_id, label_name, latest_value, sparkline_values}`
   - Violation: `sparkline_values` is declared as a Dataset row field but has no valid ColumnType representation. The ColumnType set is closed: `string`, `number`, `date`, `boolean`, `enum`. An array of floats is not in this set.
   - Required Fix: Either (a) encode sparkline_values as a serialized string and declare type: "string" with a note that the UI Implementer must parse it, or (b) remove sparkline_values from the Dataset rows and specify that the list view component fetches sparkline data separately (or that the list view is a custom component not using TableView). The architecture must state which path is chosen.

## Open Uncertainties

1. **LabelEngine uniqueness constraint behavior**
   - Location: `20_design/architecture.json` → `open_questions[1]`
   - Uncertainty: The design states that LabelEngine controls label name uniqueness but does not verify whether LabelEngine enforces global uniqueness. If it does not, two series could share a label name, breaking list view assumptions.
   - Why it matters: If LabelEngine allows duplicate names, POST /api/series could silently create two series that appear identical in the list view. The architecture relies on uniqueness without confirming it.
   - Suggested owner: Architecture

2. **Batch read window size for full vs. recent history**
   - Location: `20_design/architecture.json` → `open_questions[4]`
   - Uncertainty: The batch API is specified to return "full measurement history" in the invariants, but the open question asks whether a recent window should be the default. These are contradictory — the invariant specifies full history, but the question suggests the product may want a windowed default.
   - Why it matters: If the batch API returns full history for series with thousands of entries, the response size may be unusable for OpenClaw's stated use case. The invariant and open question should be reconciled before implementation.
   - Suggested owner: Product

## Minimal Change Set

1. Resolve the `sparkline_values` ColumnType violation: declare the list view as a custom component (not standard TableView) with sparkline_values as a serialized string field, or specify a separate sparkline data path. Update `interfaces.exposed_surfaces[GET /api/series]` and `internal_flow[step 3]`.
2. Specify the label_name retrieval path for batch_read when label_id is not in `numeric_series.series`: state that the implementer must query `labels.labels` directly for all requested label_ids unconditionally, and update `internal_flow[step 6]`.
3. Reconcile the batch API invariant ("full history") with the open question about windowed defaults — pick one and remove the contradiction.

## Approval Condition

The `sparkline_values` field must be resolved to a ColumnType-compliant representation (or the list surface must be declared as a custom non-Dataset component), and the batch_read label_name data path for unknown series must be explicitly specified.
