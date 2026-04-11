---
name: LabelEngine Sprint02_ReverseLookup Pattern
description: Surgical single-endpoint Platform sprint; IMPLEMENTATION_IN_PROGRESS; one review cycle with ordering fix
type: project
---

Sprint02_ReverseLookup added GET /api/labels/used?object_type=<str> to LabelEngine. Surgical: two existing files modified only (app/service.py, app/routers/labels.py), no new files, no schema changes.

**Why:** TaskTracker Sprint07 identified gap — no way to query "which labels are in use for tasks?" without owning the join table in the application layer.

**Design correction required:** First review (11_design_review.md) flagged ORDER BY l.name (case-sensitive) vs invariant claiming case-insensitive ordering. Fix: ORDER BY lower(l.name). Also fixed a misleading route-conflict risk note (no actual FastAPI conflict between /api/labels and /api/labels/used).

**How to apply:** For small Platform sprints modifying existing files, the scaffold step can be skipped entirely — scaffolding.json should use stub_kind: python_module_addition to signal additions-only. Ordering consistency (lower() wrapper) is a common gap when SQL is drafted before checking existing query patterns in the service.
