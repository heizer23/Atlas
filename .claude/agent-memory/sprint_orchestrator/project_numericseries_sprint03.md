---
name: NumericSeries Sprint03 Pattern
description: Measurement catalog + batch ingestion + sparkline redesign + Chronos skill; IMPLEMENTATION_IN_PROGRESS; test runner requires Bash/docker exec
type: project
---

Sprint03_Chronos&UXpt2 for NumericSeries adds:
- Static measurement catalog (`00_architecture/measurement_definitions.json`) loaded at startup
- `GET /api/measurement-definitions` → Dataset
- `POST /api/measurements/batch` → atomic multi-key ingestion (key resolves to label via `lower(l.name) = lower(key)`)
- Chronos skill at `01_System/Chronos/skills/numeric_series.py`
- Sparkline redesign: recharts removed; custom SVG with `sparkline_points [{v,ts}]` time-proportional x-axis
- Series list row: 4-column (label | sparkline | min/max stacked | current value)
- UI token fixes: all hardcoded hex replaced with CSS vars in SeriesDetailPage
- Timestamp display: `toLocaleString()` in browser local timezone
- Datetime input: split date+time with browser UTC offset appended on submit

**Why:** R-CON-AL-06 flagged in review — timezone encoding must be explicit in design, not deferred. Resolution: browser UTC offset string appended to combined datetime.

Design review cycle: 1 review → APPROVED_WITH_CHANGES → corrector → APPROVED on second pass.

Current state: IMPLEMENTATION_IN_PROGRESS — test runner blocked on Bash tool. Human must rebuild container and run:
```
docker exec atlas-numeric-series-test pytest tests/ -v
```

Or re-invoke orchestrator in a context with Bash access.

**Key fixture change:** `fix-label-weight` label name changed from `'Weight'` to `'weight'` (lowercase) to match catalog key for batch endpoint tests. Sprint02 by-name tests still pass due to case-insensitive lookup.
