---
name: TaskTracker Sprint02 Pattern
description: Sprint02 Optimization and Effort — effort field, mobile row redesign, editable detail; DESIGN_APPROVED; human gate required before implementation
type: project
---

TaskTracker Sprint02 (Optimization and Effort) reached DESIGN_APPROVED on 2026-04-05.

**Why:** Adds effort_hours field to tasks, replaces platform TableView with FoodTracker-style card list to fix mobile horizontal scroll, and makes task detail editable (app-local TaskDetailEdit replaces read-only platform DetailView).

**Key design decisions:**
- effort_hours: nullable double precision (hours), optional in create and edit
- Platform TableView and DetailView removed from tasks page — both replaced with app-local components; platform files unchanged
- PATCH nullable-clear: use Pydantic v2 `model_fields_set` to distinguish absent vs. explicitly-null for effort_hours
- Frontend: TaskDetailEdit always sends effort_hours in PATCH body (null when cleared)

**Sprint conventions:** No sprint_conventions.md exists for TaskTracker. Specs-readiness stage was skipped per user instruction (one-off deviation, not persisted as convention).

**How to apply:** If a future TaskTracker sprint continues here, the next step is `sprint_implement` after human gate confirmation. State file at `03_Application/TaskTracker/Sprint02-  Optimization and Effort/90_meta/sprint_state.json`.
