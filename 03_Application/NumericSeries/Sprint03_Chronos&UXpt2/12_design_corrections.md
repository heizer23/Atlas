# Design Corrections — numeric_series — Sprint03_Chronos&UXpt2

## Applied Changes

1. **Timezone encoding resolved for split date+time input (R-CON-AL-06)**
   - Review Source: `11_design_review.md §Blocking Issues #1`
   - Files Updated: `10_architecture.json §internal_flow[5] (datetime_input)`, `10_scaffolding.json §files SeriesDetailPage.tsx changes`
   - Change: Replaced deferred "implementer decides" with an explicit approach: frontend computes the browser UTC offset via `Date.getTimezoneOffset()` and appends it as a signed offset string (e.g. `+02:00`) to the combined datetime value before sending to the backend. Architecture now declares: user's local clock is the time authority; the browser offset string makes the timezone explicit; Postgres stores as TIMESTAMPTZ (converting to UTC internally). The previously-open question about timezone encoding is removed from `open_questions`. The risk entry is updated to reflect the narrower DST boundary edge case that remains.

2. **`series.py` LIST_SCHEMA added to scaffolding (R-CON-BP-09)**
   - Review Source: `11_design_review.md §Blocking Issues #2`
   - Files Updated: `10_scaffolding.json §files`
   - Change: Added `backend/routers/series.py` as a `changed` file entry. Specifies: remove `sparkline_values` column from `LIST_SCHEMA`; add `sparkline_points` (string), `min_value` (number), `max_value` (number) columns. This ensures the frontend column schema matches the row fields that the updated service will return.

## Unchanged by Design

All other sections of `10_architecture.json`, `10_scaffolding.json`, `10_schema.sql`, and `10_test_spec.md` were preserved verbatim. The test spec does not require changes as the sparkline_points test scenario already references the correct field name.

## Review Alignment Check

- Minimal Change Set Applied: Yes
- Approval Condition Satisfied: Yes (both blocking issues resolved; timezone encoding is now explicit in the architecture with a declared approach; series.py scaffolding entry now lists LIST_SCHEMA changes)
- Notes: None — no human attention required.
