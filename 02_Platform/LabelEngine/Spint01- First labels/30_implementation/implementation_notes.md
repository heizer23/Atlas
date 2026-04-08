# LabelEngine Sprint01 — Implementation Notes

**Date:** 2026-04-07
**Implementer:** Application_Implementer (claude-sonnet-4-6)

---

## Scaffold status

The scaffold generator had not run before implementation. All files listed in `20_design/scaffolding.json` were created during this implementation pass. The sprint folder name has a typo (`Spint01-` not `Sprint01-`); implementation preserves the existing folder name to avoid breaking the schema.sql path reference.

---

## Case sensitivity for label name matching

**Decision:** Case-insensitive matching everywhere.

- `GET /api/labels?q=` uses `lower(name) LIKE lower(q) || '%'` which hits the `ix_labels_name_lower` functional index.
- `_resolve_or_create_label` (used by attach) uses `lower(name) = lower(label_name)` for exact match before deciding to insert.
- `POST /api/labels` inserts the name exactly as supplied (after strip). If a caller creates "Outside" then later creates "outside", they will be two separate labels. Callers using the attach endpoint get case-insensitive deduplication automatically. Direct create via `POST /api/labels` bypasses this; callers should prefer attach for label-and-associate workflows.

**Rationale:** UX consistency — 'outside' and 'Outside' should resolve to the same label in the common attach flow. The direct-create path does not deduplicate by design; it is a power-user path.

---

## AttachLabelRequest includes object_type

The architecture declares `AttachLabelRequest.label_name: str` but the `object_labels` table requires `object_type NOT NULL`. The design does not define a separate objects registry in LabelEngine (unlike LinkingEngine which has `linking.objects`).

**Decision:** `object_type` is added as a required field on `AttachLabelRequest`. The DB CHECK constraint rejects non-lowercase values, consistent with the architecture invariant. Callers (e.g. TaskTracker) supply `object_type: "task"`.

This is a minor design gap: the architecture's `AttachLabelRequest` shape only listed `label_name`. The addition is necessary for the DB schema to work. It is a non-breaking extension from the caller's perspective — callers already know their object type.

---

## Pagination for GET /api/groups

Model: **paginate items before grouping**.

1. Count `distinct object_id` for the requested `object_type` (unpaginated total).
2. Select the page slice using `order by object_id` + `limit/offset`. The ordering is by `object_id` (stable, deterministic). This is not semantically meaningful ordering for UI purposes; a later sprint may add ordering by `title` or `created_at` via a join to the application's own object table.
3. Fetch primary label and all labels for objects in the slice only.
4. Group, sort named groups alphabetically, append Unlabeled last.

`meta.total` = unpaginated count of distinct objects with this type.
`meta.page_count` = `ceil(total / page_size)`.

**Why paginate before grouping:** Groups can span pages. A "Work" group with 200 tasks would consume the entire first page if groups were paginated. Paginating items first allows callers to render progressively, with groups appearing/growing as pages are loaded. This matches the architecture's explicit resolution in `deferred_decisions[0]`.

---

## Primary label resolution

Uses PostgreSQL `DISTINCT ON (object_id) ... ORDER BY object_id, attached_at ASC, label_id ASC`. This resolves primary label in a single query pass, avoiding a subquery with `MIN()`.

Both approaches are correct. `DISTINCT ON` is more readable and performs well with the `ix_object_labels_type_obj_time` composite index (object_type, object_id, attached_at, label_id).

---

## _resolve_or_create_label and transaction boundaries

The `_resolve_or_create_label` helper commits inside itself (for the insert path) before returning. The outer `attach_label` method then inserts the `object_labels` row and commits again. This means two commits per new-label attach:

1. Commit 1: insert label → returns label_id
2. Commit 2: insert object_labels row → returns ObjectLabelRecord

A race between two concurrent requests for the same label name could result in two label rows being created if both read "not found" before either commits. The probability is low (prefix queries on a typeahead UI are typically sequential). A `ON CONFLICT DO NOTHING` on a unique index for `lower(name)` would close this window, but `labels.labels` does not have such an index in v1 (the design explicitly allows duplicate names on direct create). The attach path uses case-insensitive lookup as a best-effort deduplication; it is not a hard uniqueness guarantee.

This is consistent with the architecture's non-goal list and the direct-create note above. A later sprint may add a unique index on `lower(name)` if strict deduplication is required.

---

## GET /health

Added at `/health` (not `/api/health`) per convention and the orchestrator constraint. Returns `{"status": "ok"}` with HTTP 200.

---

## Port

Port 8050 as specified. LinkingEngine is on 8040. No collision detected with existing services.

---

## Schema path

`init_schema` looks for `20_Data/schema.sql` relative to the sprint folder alongside the LabelEngine root. The sprint folder name `Spint01- First labels` (note typo) is preserved exactly. An inline DDL fallback is provided for deployments where the sprint folder is absent.

---

## No domain logic

LabelEngine contains no workflow rules, status transitions, or application-specific meaning. It stores and queries labels and attachments only. Domain interpretation is deferred entirely to callers (e.g. TaskTracker).
