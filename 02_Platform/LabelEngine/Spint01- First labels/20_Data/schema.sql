-- LabelEngine schema
-- Source of truth: 20_design/architecture.json persistence
-- Sprint01 — First labels

create schema if not exists labels;

-- ── labels.labels ─────────────────────────────────────────────────────────────
-- Stores named labels. No hierarchy, no metadata, no colors in v1.
-- Duplicates by name are allowed unless the application enforces uniqueness
-- via the case-insensitive lookup in service.py attach_label / create_label.

create table if not exists labels.labels (
    id         text        not null default gen_random_uuid()::text,
    name       text        not null,
    created_at timestamptz not null default now(),
    constraint labels_pkey primary key (id),
    constraint labels_name_nonempty check (length(trim(name)) > 0)
);

create index if not exists ix_labels_name_lower
    on labels.labels (lower(name));

-- ── labels.object_labels ──────────────────────────────────────────────────────
-- Many-to-many attachment table.
--
-- attached_at: records when this label was first attached to this object.
-- This column is the basis for the primary-label rule:
--   the label with the minimum attached_at for a given object_id is the primary label.
-- Ties are broken by label_id ASC to ensure full determinism.
--
-- object_type: the domain type of the object (e.g. 'task'). Stored here to
-- allow grouped queries to be scoped by type without joining to an external table.
-- Values must be lowercase — callers are responsible for supplying lowercase values.
-- LabelEngine enforces this via the CHECK constraint below.

create table if not exists labels.object_labels (
    object_id   text        not null,
    label_id    text        not null references labels.labels(id),
    object_type text        not null,
    attached_at timestamptz not null default now(),
    constraint object_labels_pkey primary key (object_id, label_id),
    constraint object_labels_object_type_lowercase check (object_type = lower(object_type))
);

create index if not exists ix_object_labels_object_id
    on labels.object_labels (object_id);

create index if not exists ix_object_labels_label_id
    on labels.object_labels (label_id);

create index if not exists ix_object_labels_object_type
    on labels.object_labels (object_type);

-- Composite index to support primary-label resolution query:
-- SELECT object_id, label_id, attached_at FROM labels.object_labels
-- WHERE object_type = $1 ORDER BY object_id, attached_at, label_id
create index if not exists ix_object_labels_type_obj_time
    on labels.object_labels (object_type, object_id, attached_at, label_id);
