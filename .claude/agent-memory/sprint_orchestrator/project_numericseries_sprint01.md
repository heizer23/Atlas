---
name: NumericSeries Sprint01 Pattern
description: Numeric measurement series app; recharts sparkline; AWAITING_HUMAN_REVIEW; human gate required before sprint_implement_reviewer
type: project
---

NumericSeries Sprint01 implemented a user-facing time-series measurement tracker backed by LabelEngine for label names.

**State at handoff:** AWAITING_HUMAN_REVIEW

**Key decisions:**
- sparkline_values encoded as JSON string (ColumnType: "string") to comply with UI Data Contract closed ColumnType set; UI must parse
- SeriesListPage uses recharts LineChart at height=28 as inline sparkline (react-sparklines not installed in shell)
- POST /api/series/{label_id}/values (external write) with unknown label_id → 404 SERIES_NOT_FOUND (conservative default)
- Port: 8014, container: atlas-numeric-series
- Partial backend was pre-existing when orchestrator resumed (database.py, models.py, service.py, label_client.py, routers/series.py)
- Agent tool unavailable in this environment; orchestrator implemented directly

**Human gate:** Required before sprint_implement_reviewer. Human must confirm review before invoking reviewer.

**Why:** Design review passed after one correction loop (sparkline_values ColumnType fix, batch_read label retrieval path fix). Second review: APPROVED.
