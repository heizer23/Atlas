# Design Review — numeric_series — Sprint03_Chronos&UXpt2

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-04-12
**Reviewer:** sprint_design_reviewer

## Blocking Issues

| # | Location | Rule / Contract Violated | Required Change |
|---|----------|--------------------------|-----------------|
| 1 | `10_architecture.json §internal_flow[5] (datetime_input)` + `10_architecture.json §open_questions[0]` | R-CON-AL-06 Time Authority — design must declare the authoritative time source and explain how consistency is maintained; "implementer decides" is not a valid resolution | The design must resolve the timezone encoding for the combined datetime value. Choose one: (a) append 'Z' (UTC — user must enter time in UTC); (b) append browser UTC offset string using `new Date().getTimezoneOffset()` (local time preserved); (c) leave as naive local (document that server will interpret as UTC and accept the divergence as a known limitation). The chosen approach must be stated in the architecture, not deferred. |
| 2 | `10_scaffolding.json §files[4] (service.py)` — `LIST_SCHEMA` in `backend/routers/series.py` not listed as a changed file | R-CON-BP-09 Cross-Artifact Truth Consistency — the scaffolding changes `sparkline_values` → `sparkline_points` in the service, but `series.py`'s `LIST_SCHEMA` still declares `sparkline_values: string` as a column key; this column key mismatch will cause the frontend to receive `sparkline_points` in the row but look for `sparkline_values` in the schema | Add `backend/routers/series.py` to the `files` list in `10_scaffolding.json` with a `changed` entry explicitly listing: (a) update `LIST_SCHEMA` to replace `sparkline_values` with `sparkline_points`, and add `min_value` (number) and `max_value` (number) columns; (b) note that `sparkline_points` is ColumnType `string` (JSON-encoded). |

## Non-Blocking Issues

| # | Location | Observation |
|---|----------|-------------|
| 1 | `10_architecture.json §internal_flow[4] (sparkline_data)` | The flow states ts is "Unix epoch milliseconds" but the scaffolding service change says `int(recorded_at.timestamp() * 1000)` — this requires the database cursor to return a datetime object, not the existing `recorded_at::text` cast. The implementer needs to change the SQL cast from `::text` to return a native datetime. Non-blocking because the scaffolding defers this to the implementer, but the architecture could make the SQL cast change explicit. |
| 2 | `10_scaffolding.json §files[6] (01_System/Chronos/skills/numeric_series.py)` | The directory `01_System/Chronos/skills/` is assumed to exist but is not confirmed in the dev reference (Chronos is marked stub). The implementer should verify this path exists before writing. |

## Approval Condition

Both blocking issues must be resolved in the corrected design before implementation proceeds: (1) explicit timezone encoding strategy for the split date+time input declared in architecture.json, and (2) `series.py` added to scaffolding with LIST_SCHEMA update to `sparkline_points`, `min_value`, `max_value`.
