---
name: LabelEngine Sprint02 Pattern
description: Batch read endpoint sprint for LabelEngine; AWAITING_HUMAN_REVIEW; no design gaps; route ordering risk mitigated
type: project
---

Sprint02_Batch_Read adds POST /api/objects/labels/batch to the existing LabelEngine platform service.

**Why:** F-001 audit finding — TaskTracker was bypassing LabelEngine API and querying labels.* schema directly via SQL. Root cause: no batch endpoint existed, making N sequential HTTP calls impractical.

**Key implementation decisions:**
- `BatchLabelRecord.id` is `label_id` from the DB row (not `object_id`) — matches draft shape `{ id, name, attached_at }`
- Route ordering: `/objects/labels/batch` registered before `/objects/{object_id}/labels` in `app/routers/objects.py` to prevent FastAPI path-param shadowing
- Zero-fill initialised from input `object_ids` list in `LabelService.get_labels_for_objects`, not from DB result set
- Single `ANY(%s)` query — no N+1

**State:** AWAITING_HUMAN_REVIEW
Human gate required before sprint_implement_reviewer is invoked.

**Sprint folder:** `02_Platform/LabelEngine/Sprint02_Batch_Read/`

**How to apply:** When orchestrating future LabelEngine sprints, note this endpoint is live and available to consuming applications via `_label_client()`.
