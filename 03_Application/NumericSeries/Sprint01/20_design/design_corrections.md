# Design Corrections — numeric_series

## Applied Changes

1. **sparkline_values ColumnType violation resolved**
   - Review Source: `20_design/design_review.md` → Confirmed Problems #1, Hard Rule Violations #1, Minimal Change Set item 1
   - Files Updated: `20_design/architecture.json`
   - Change: `interfaces.exposed_surfaces[GET /api/series]` updated to declare sparkline_values as ColumnType 'string' (JSON-encoded float array) and to note that SeriesListPage must use a custom component, not standard platform TableView. `internal_flow[step 3]` updated to specify that sparkline_values is serialized as a JSON string in the Dataset row, and that the UI Implementer must parse it.

2. **batch_read label_name retrieval path for unknown series specified**
   - Review Source: `20_design/design_review.md` → Confirmed Problems #2, Minimal Change Set item 2
   - Files Updated: `20_design/architecture.json`, `20_design/scaffolding.json`
   - Change: `internal_flow[step 6]` updated to specify that the backend queries `labels.labels` unconditionally for all requested label_ids, not only those in `numeric_series.series`. label_name is null for label_ids absent from `labels.labels`. `scaffolding.json` `assemble_batch` method purpose updated to match. `BatchSeriesEntry.label_name` type changed from `str` to `str | None`.

3. **Batch API invariant vs. windowed-default open question reconciled**
   - Review Source: `20_design/design_review.md` → Open Uncertainties #2, Minimal Change Set item 3
   - Files Updated: `20_design/architecture.json`
   - Change: Invariant updated to explicitly state "full measurement history is returned for each series (no windowing)". Open question #5 updated to reflect resolution (full history, no windowing in this slice).

## Unchanged by Design
- All other sections of `architecture.json` and `scaffolding.json` were preserved verbatim. `20_Data/schema.sql` was not touched. The draft definition alignment, layer classification, dependency list, persistence model, deferrals, and all other open questions are unchanged.

## Review Alignment Check
- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes — sparkline_values is now declared as ColumnType 'string' with explicit custom-component note; batch_read label_name data path is fully specified; batch API invariant and open question are reconciled.
- Notes: The recommended improvement about non-atomic creation recovery path (Recommended Improvements #2) was not applied as it was not in the Minimal Change Set and is not marked as required before implementation.
