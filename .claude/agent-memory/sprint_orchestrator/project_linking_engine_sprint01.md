---
name: LinkingEngine Sprint01 Pattern
description: First sprint for the Platform-layer LinkingEngine component; generic object-linking service; reached AWAITING_HUMAN_REVIEW with full implementation
type: project
---

LinkingEngine Sprint01_First Linking reached AWAITING_HUMAN_REVIEW on 2026-04-06.

**Why:** First sprint for a new Platform component providing generic object-linking (task-to-task initially, extensible to workout/meal). Drafted as a comprehensive 23-section spec.

**Sprint path:** `02_Platform/LinkingEngine/Sprint01_First Linking/`

**Key patterns observed:**
- App code (models.py, service.py, database.py) was substantially pre-implemented before the sprint formally ran. The sprint process ran correctly regardless — design artifacts were produced fresh and the implementation completed the missing files (main.py, routers, compose.yml, Dockerfile).
- No sprint_conventions.md — canonical process applied.
- `sprint_implement` agent is used for Platform layer (no separate platform implementer agent exists).
- Port 8040 chosen for compose.yml — unverified against central registry.
- The draft's `/tasks/{task_id}/links` endpoint path was correctly genericized to `/linking/objects/{object_id}/links` by the platform designer.

**Design decisions captured:**
- `linking` schema in shared Postgres (pattern: tasktracker, calendar schemas)
- workspace_id nullable — null treated as "workspace not enforced" (existing Atlas pattern)
- register_object() is the integration contract for consuming applications
- relation normalization is always backend-only (invariant)
- Non-directional links stored with lexicographically smaller ID as from_object_id

**Human gate required before sprint_implement_reviewer.**

**How to apply:** When routing Platform sprints with pre-existing code, verify existing code against design artifacts rather than regenerating. sprint_implement still runs to complete missing deployment/entrypoint files.
