"""
LabelEngine — LabelService.

All label business logic: search, create, attach, remove, get-for-object,
grouped-query with primary-label resolution.

No HTTP concerns live here — this module is pure domain + SQL.

Source of truth: 20_design/architecture.json internal_flow + interfaces.provides
"""

from __future__ import annotations

import math

import psycopg2.extensions

from app.models import (
    BatchLabelRecord,
    GroupedMeta,
    GroupedObjectsResponse,
    GroupItem,
    LabelGroup,
    LabelRecord,
    ObjectLabelRecord,
)


class LabelEngineError(Exception):
    """Raised by LabelService for known failure modes."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code    = code
        self.message = message
        self.status  = status


class LabelService:

    # ── Label search ──────────────────────────────────────────────────────────

    def search_labels(
        self,
        conn: psycopg2.extensions.connection,
        q: str,
    ) -> list[LabelRecord]:
        """
        Return labels whose name starts with q (case-insensitive prefix match).
        Empty q returns all labels, ordered by name.

        Uses ix_labels_name_lower index via lower(name) LIKE lower(q) || '%'.
        """
        with conn.cursor() as cur:
            if q:
                prefix = q.strip().lower() + "%"
                cur.execute(
                    "select id, name from labels.labels"
                    " where lower(name) like %s"
                    " order by lower(name)",
                    (prefix,),
                )
            else:
                cur.execute(
                    "select id, name from labels.labels order by lower(name)"
                )
            rows = cur.fetchall()

        return [LabelRecord(id=r["id"], name=r["name"]) for r in rows]

    # ── Label creation ────────────────────────────────────────────────────────

    def create_label(
        self,
        conn: psycopg2.extensions.connection,
        name: str,
    ) -> LabelRecord:
        """
        Insert a new label. Caller must have already validated name is non-empty.
        Returns the created LabelRecord.
        """
        with conn.cursor() as cur:
            cur.execute(
                "insert into labels.labels (name) values (%s)"
                " returning id, name",
                (name,),
            )
            row = cur.fetchone()
        conn.commit()
        return LabelRecord(id=row["id"], name=row["name"])

    # ── Label attach ──────────────────────────────────────────────────────────

    def attach_label(
        self,
        conn: psycopg2.extensions.connection,
        object_id: str,
        object_type: str,
        label_name: str,
    ) -> ObjectLabelRecord:
        """
        Resolve or create a label by name (case-insensitive exact match),
        then idempotently attach it to object_id.

        Returns the ObjectLabelRecord for the (object_id, label_id) pair
        whether newly inserted or pre-existing.

        object_type must be lowercase — the DB CHECK constraint will reject it otherwise.
        label_name must be non-empty after strip — caller validates this.
        """
        label_id = self._resolve_or_create_label(conn, label_name)

        with conn.cursor() as cur:
            # Idempotent insert
            cur.execute(
                """
                insert into labels.object_labels (object_id, label_id, object_type)
                values (%s, %s, %s)
                on conflict (object_id, label_id) do nothing
                """,
                (object_id, label_id, object_type),
            )
            # Fetch the canonical row (whether just inserted or pre-existing)
            cur.execute(
                """
                select ol.object_id, ol.label_id, l.name as label_name,
                       ol.attached_at
                from labels.object_labels ol
                join labels.labels l on l.id = ol.label_id
                where ol.object_id = %s and ol.label_id = %s
                """,
                (object_id, label_id),
            )
            row = cur.fetchone()
        conn.commit()

        return ObjectLabelRecord(
            object_id   = row["object_id"],
            label_id    = row["label_id"],
            label_name  = row["label_name"],
            attached_at = row["attached_at"].isoformat(),
        )

    # ── Label remove ──────────────────────────────────────────────────────────

    def remove_label(
        self,
        conn: psycopg2.extensions.connection,
        object_id: str,
        label_id: str,
    ) -> None:
        """
        Delete the (object_id, label_id) attachment row.
        Raises LabelEngineError(ATTACHMENT_NOT_FOUND, 404) if absent.
        Raises LabelEngineError(LABEL_NOT_FOUND, 404) if label_id does not exist.
        """
        with conn.cursor() as cur:
            # Check label exists first
            cur.execute(
                "select id from labels.labels where id = %s",
                (label_id,),
            )
            if cur.fetchone() is None:
                raise LabelEngineError(
                    code    = "LABEL_NOT_FOUND",
                    message = f"Label '{label_id}' does not exist.",
                    status  = 404,
                )

            cur.execute(
                "delete from labels.object_labels"
                " where object_id = %s and label_id = %s"
                " returning object_id",
                (object_id, label_id),
            )
            deleted = cur.fetchone()

        if deleted is None:
            raise LabelEngineError(
                code    = "ATTACHMENT_NOT_FOUND",
                message = f"Label '{label_id}' is not attached to object '{object_id}'.",
                status  = 404,
            )
        conn.commit()

    # ── Labels for object ─────────────────────────────────────────────────────

    def get_labels_for_object(
        self,
        conn: psycopg2.extensions.connection,
        object_id: str,
    ) -> list[ObjectLabelRecord]:
        """
        Return all labels attached to object_id, ordered by attached_at ASC,
        label_id ASC (mirrors the primary-label tiebreaker ordering).
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                select ol.object_id, ol.label_id, l.name as label_name,
                       ol.attached_at
                from labels.object_labels ol
                join labels.labels l on l.id = ol.label_id
                where ol.object_id = %s
                order by ol.attached_at asc, ol.label_id asc
                """,
                (object_id,),
            )
            rows = cur.fetchall()

        return [
            ObjectLabelRecord(
                object_id   = r["object_id"],
                label_id    = r["label_id"],
                label_name  = r["label_name"],
                attached_at = r["attached_at"].isoformat(),
            )
            for r in rows
        ]

    # ── Grouped object query ──────────────────────────────────────────────────

    def get_grouped_objects(
        self,
        conn: psycopg2.extensions.connection,
        object_type: str,
        page: int,
        page_size: int,
    ) -> GroupedObjectsResponse:
        """
        Return objects of object_type grouped by primary label.

        Pagination model: paginate the flat ordered object list BEFORE grouping.
          1. Count total distinct objects of this type (unpaginated).
          2. Select the page slice (offset/limit) from the ordered flat list.
          3. For each object in the slice, determine primary label and all labels.
          4. Group, sort alphabetically, append Unlabeled last.

        Primary label = label with MIN(attached_at) for that object_id.
        Ties broken by label_id ASC.
        """
        offset = (page - 1) * page_size

        with conn.cursor() as cur:
            # Step 1: total count of distinct objects with this type
            cur.execute(
                """
                select count(distinct object_id) as total
                from labels.object_labels
                where object_type = %s
                """,
                (object_type,),
            )
            total = cur.fetchone()["total"]

            # Step 2: ordered flat object list, paginated
            cur.execute(
                """
                select distinct object_id
                from labels.object_labels
                where object_type = %s
                order by object_id
                limit %s offset %s
                """,
                (object_type, page_size, offset),
            )
            page_object_ids = [r["object_id"] for r in cur.fetchall()]

            if not page_object_ids:
                page_count = math.ceil(total / page_size) if page_size > 0 else 0
                return GroupedObjectsResponse(
                    meta=GroupedMeta(
                        total=total,
                        page=page,
                        page_size=page_size,
                        page_count=page_count,
                    ),
                    groups=[],
                )

            # Step 3a: primary label for each object in the page slice
            # MIN(attached_at) + label_id ASC tiebreaker
            cur.execute(
                """
                select distinct on (ol.object_id)
                    ol.object_id,
                    ol.label_id,
                    l.name as label_name
                from labels.object_labels ol
                join labels.labels l on l.id = ol.label_id
                where ol.object_id = any(%s)
                order by ol.object_id, ol.attached_at asc, ol.label_id asc
                """,
                (page_object_ids,),
            )
            primary_rows = cur.fetchall()
            primary_label: dict[str, str] = {
                r["object_id"]: r["label_name"] for r in primary_rows
            }

            # Step 3b: all labels for each object in the page slice
            cur.execute(
                """
                select ol.object_id, l.name as label_name
                from labels.object_labels ol
                join labels.labels l on l.id = ol.label_id
                where ol.object_id = any(%s)
                order by ol.attached_at asc, ol.label_id asc
                """,
                (page_object_ids,),
            )
            all_label_rows = cur.fetchall()
            all_labels: dict[str, list[str]] = {}
            for r in all_label_rows:
                all_labels.setdefault(r["object_id"], []).append(r["label_name"])

        # Step 4: group assembly
        named_groups: dict[str, list[GroupItem]] = {}
        unlabeled_items: list[GroupItem] = []

        for obj_id in page_object_ids:
            plabel = primary_label.get(obj_id)
            item = GroupItem(
                id            = obj_id,
                primary_label = plabel,
                labels        = all_labels.get(obj_id, []),
            )
            if plabel is None:
                unlabeled_items.append(item)
            else:
                named_groups.setdefault(plabel, []).append(item)

        # Named groups alphabetically, then Unlabeled last
        groups = [
            LabelGroup(label=name, items=items)
            for name, items in sorted(named_groups.items())
        ]
        if unlabeled_items:
            groups.append(LabelGroup(label="Unlabeled", items=unlabeled_items))

        page_count = math.ceil(total / page_size) if page_size > 0 else 0

        return GroupedObjectsResponse(
            meta=GroupedMeta(
                total=total,
                page=page,
                page_size=page_size,
                page_count=page_count,
            ),
            groups=groups,
        )

    # ── Batch label read ──────────────────────────────────────────────────────

    def get_labels_for_objects(
        self,
        conn: psycopg2.extensions.connection,
        object_ids: list[str],
        object_type: str,
    ) -> dict[str, list[BatchLabelRecord]]:
        """
        Return labels for a set of object_ids filtered by object_type.

        Uses a single ANY(%s) query. Result dict is zero-filled: every
        requested object_id appears as a key, even if no labels are attached.
        Labels within each list are ordered by attached_at ASC, label_id ASC
        (consistent with get_labels_for_object ordering).

        Caller must validate that object_ids is non-empty before calling this
        method (the router short-circuits on empty input).
        """
        # Initialise zero-fill result from input list
        result: dict[str, list[BatchLabelRecord]] = {oid: [] for oid in object_ids}

        with conn.cursor() as cur:
            cur.execute(
                """
                select ol.object_id, ol.label_id, l.name as label_name,
                       ol.attached_at
                from labels.object_labels ol
                join labels.labels l on l.id = ol.label_id
                where ol.object_id = any(%s)
                  and ol.object_type = %s
                order by ol.attached_at asc, ol.label_id asc
                """,
                (object_ids, object_type),
            )
            rows = cur.fetchall()

        for r in rows:
            oid = r["object_id"]
            if oid in result:
                result[oid].append(
                    BatchLabelRecord(
                        id          = r["label_id"],
                        name        = r["label_name"],
                        attached_at = r["attached_at"].isoformat(),
                    )
                )

        return result

    # ── Reverse lookup ───────────────────────────────────────────────────────

    def get_labels_used_by_type(
        self,
        conn: psycopg2.extensions.connection,
        object_type: str,
    ) -> list[LabelRecord]:
        """
        Return all distinct labels attached to at least one object of
        the given object_type, ordered by lower(name) ascending.
        Returns an empty list if no labels are attached to any such object.

        Uses ix_object_labels_object_type index for the WHERE clause.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, name from (
                    select distinct l.id, l.name, lower(l.name) as sort_key
                    from labels.labels l
                    join labels.object_labels ol on ol.label_id = l.id
                    where ol.object_type = %s
                ) sub
                order by sort_key
                """,
                (object_type,),
            )
            rows = cur.fetchall()

        return [LabelRecord(id=r["id"], name=r["name"]) for r in rows]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_or_create_label(
        self,
        conn: psycopg2.extensions.connection,
        name: str,
    ) -> str:
        """
        Case-insensitive exact match on label name.
        If found, return existing label_id.
        If not found, insert new label and return generated label_id.

        Decision: case-insensitive matching — 'outside' and 'Outside' resolve to
        the same label. This is consistent with GET /api/labels?q= prefix search.
        See implementation_notes.md §Case sensitivity.
        """
        with conn.cursor() as cur:
            cur.execute(
                "select id from labels.labels where lower(name) = lower(%s) limit 1",
                (name,),
            )
            row = cur.fetchone()
            if row:
                return row["id"]

            cur.execute(
                "insert into labels.labels (name) values (%s) returning id",
                (name,),
            )
            row = cur.fetchone()
        conn.commit()
        return row["id"]
