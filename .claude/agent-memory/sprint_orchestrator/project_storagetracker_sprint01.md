---
name: StorageTracker Sprint01 Pattern
description: First sprint for StorageTracker; full automated loop from DRAFT_READY to SPRINT_COMPLETE; port collision with Notifications (8020) corrected to 8022
type: project
---

StorageTracker Sprint01_Core completed 2026-04-11 in a fully automated loop.

**Why:** New component, no existing baseline. FastAPI + PostgreSQL + React, same pattern as TaskTracker.

**Port:** 8022 (8020 was already taken by Notifications, 8021 by CalendarConnector).

**Design loop:** One correction round. Two non-blocking doc issues caught by reviewer: (1) schema_artifact referenced sprint folder path instead of component-root path; (2) search q param described as "required" but contract says optional.

**Tests:** 27 test cases written in tests/test_items.py, covering all endpoints including route ordering, auto-transition, history, and partial update semantics. Cannot be run on host — Python packages only available inside Docker containers. Run with:
  PYTHONPATH=02_Platform/packages ATLAS_PG_HOST=127.0.0.1 ATLAS_PG_PASSWORD=... pytest 03_Application/StorageTracker/tests/ -v

**Key implementation decisions:**
- Route ordering: /items/views/* registered BEFORE /items/{item_id} to prevent FastAPI path param collision
- Auto-transition: caller-supplied state always wins; auto-transition only fires if state not in model_fields_set (PATCH) or state == "stored" (POST)
- source_tags stored as jsonb; filter uses @> array containment operator
- History recorded per changed field (state_change, location_change, quantity_change separately)
- GET /items/{id} embeds last 20 history entries in row["history"]

**How to apply:** When routing to future StorageTracker sprints, check port 8022 is still correct and use this sprint as architecture baseline.
