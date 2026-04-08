"""
LinkingEngine — LinkService.

Business logic for link creation, validation, normalization, and grouped retrieval.
DB access: module-level get_db() context manager (TaskTracker/CalendarConnector pattern).

Source of truth: 20_design/architecture.json internal_flow + interfaces.provides
"""

from __future__ import annotations

from app.database import get_db
from app.models import (
    CreateLinkRequest,
    LinkGroup,
    LinkGroupItem,
    LinkRecord,
    ObjectRecord,
    RelationDefinition,
)


# ── Normalization table ───────────────────────────────────────────────────────
# Maps free-text user input variants to canonical relation keys.
# Source: 00_input/draft.md section 12.
# Extend this dict when new relation types are added to relation_definitions.

_NORMALIZATION_MAP: dict[str, str] = {
    # subtask_of variants
    "subtask":       "subtask_of",
    "sub task":      "subtask_of",
    "subtask of":    "subtask_of",
    "subtask_of":    "subtask_of",
    "child task":    "subtask_of",
    "child":         "subtask_of",
    "parent task":   "subtask_of",  # UI shows "Parent Task" label; accept as input too
    # related_to variants
    "related":       "related_to",
    "related to":    "related_to",
    "related_to":    "related_to",
    "relates to":    "related_to",
}


class LinkService:

    def __init__(self) -> None:
        # No constructor arguments.
        # All methods use module-level get_db() context manager directly,
        # matching the TaskTracker and CalendarConnector DB access pattern.
        pass

    # ── Normalization ─────────────────────────────────────────────────────────

    def normalize_relation_input(self, relation_input: str) -> str | None:
        """Map free-text input to canonical relation_key. Return None if unrecognized."""
        return _NORMALIZATION_MAP.get(relation_input.strip().lower())

    # ── Object registration ───────────────────────────────────────────────────

    def register_object(
        self,
        object_id: str,
        object_type: str,
        workspace_id: str | None,
        title: str | None,
    ) -> None:
        """
        Upsert a row in linking.objects.

        Call this from application code on entity creation AND on title update
        to keep linking.objects.title in sync with the source table.
        (Ref: design_review2.md open uncertainty — title synchronization.)
        """
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into linking.objects (object_id, workspace_id, type, title, updated_at)
                    values (%s, %s, %s, %s, now())
                    on conflict (object_id) do update
                        set title        = excluded.title,
                            workspace_id = excluded.workspace_id,
                            updated_at   = now()
                    """,
                    (object_id, workspace_id, object_type, title),
                )
            conn.commit()

    # ── Link creation ─────────────────────────────────────────────────────────

    def create_link(self, request: CreateLinkRequest) -> LinkRecord:
        """
        Validate, normalize direction, enforce constraints, and insert link row.
        Raises ValueError with error code string on any validation failure.

        Internal flow (20_design/architecture.json steps 1–5):
          1. normalize_relation_input
          2. resolve_objects
          3. validate_link
          4. apply_canonical_direction
          5. insert_link
        """
        # Step 1: normalize relation input
        relation_key = self.normalize_relation_input(request.relation_input)
        if relation_key is None:
            raise ValueError("RELATION_INPUT_UNRECOGNIZED")

        with get_db() as conn:
            with conn.cursor() as cur:
                # Step 2: resolve objects
                cur.execute(
                    "select object_id, workspace_id, type, title from linking.objects where object_id = %s",
                    (request.source_object_id,),
                )
                from_obj = cur.fetchone()
                if from_obj is None:
                    raise ValueError("OBJECT_NOT_FOUND")

                cur.execute(
                    "select object_id, workspace_id, type, title from linking.objects where object_id = %s",
                    (request.target_object_id,),
                )
                to_obj = cur.fetchone()
                if to_obj is None:
                    raise ValueError("OBJECT_NOT_FOUND")

                # Step 2b: self-link check
                if request.source_object_id == request.target_object_id:
                    raise ValueError("SELF_LINK_NOT_ALLOWED")

                # Step 3a: fetch relation definition
                cur.execute(
                    "select * from linking.relation_definitions where key = %s and is_active = true",
                    (relation_key,),
                )
                rel_def = cur.fetchone()
                if rel_def is None:
                    raise ValueError("INVALID_RELATION")

                # Step 3b: type pair check
                if (
                    from_obj["type"] not in rel_def["allowed_from_types"]
                    or to_obj["type"] not in rel_def["allowed_to_types"]
                ):
                    raise ValueError("INVALID_OBJECT_TYPE_PAIR")

                # Step 3c: cycle check (directional relations only — direct reverse)
                if rel_def["is_directional"]:
                    if _check_cycle(
                        cur,
                        request.source_object_id,
                        request.target_object_id,
                        relation_key,
                        request.workspace_id,
                    ):
                        raise ValueError("CYCLE_DETECTED")

                # Step 4: apply canonical direction
                canonical_from, canonical_to = _apply_canonical_direction(
                    request.source_object_id,
                    request.target_object_id,
                    rel_def["is_directional"],
                )

                # Step 5: insert link
                cur.execute(
                    """
                    insert into linking.object_links
                        (workspace_id, from_object_id, to_object_id, relation_key,
                         created_by_type, created_by_id, confidence)
                    values (%s, %s, %s, %s, %s, %s, 1.0)
                    returning id, workspace_id, from_object_id, to_object_id, relation_key,
                              created_by_type, created_by_id, confidence, archived_at, created_at
                    """,
                    (
                        request.workspace_id,
                        canonical_from,
                        canonical_to,
                        relation_key,
                        request.created_by_type,
                        request.created_by_id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        return LinkRecord(
            link_id         = str(row["id"]),
            from_object_id  = row["from_object_id"],
            to_object_id    = row["to_object_id"],
            relation_key    = row["relation_key"],
            created_by_type = row["created_by_type"],
            created_by_id   = row["created_by_id"],
            confidence      = float(row["confidence"]),
            archived_at     = row["archived_at"].isoformat() if row["archived_at"] else None,
            created_at      = row["created_at"].isoformat(),
        )

    # ── Grouped link retrieval ────────────────────────────────────────────────

    def get_links_for_object(
        self,
        object_id: str,
        workspace_id: str | None = None,
    ) -> list[LinkGroup]:
        """
        Fetch all active links for object_id, resolve forward/reverse labels,
        group by display label ordered by sort_order.

        Internal flow: architecture.json step 6.
        """
        with get_db() as conn:
            with conn.cursor() as cur:
                # Fetch all active links where this object appears on either side
                cur.execute(
                    """
                    select
                        ol.id,
                        ol.from_object_id,
                        ol.to_object_id,
                        ol.relation_key,
                        rd.forward_label,
                        rd.reverse_label,
                        rd.is_directional,
                        rd.sort_order
                    from linking.object_links ol
                    join linking.relation_definitions rd on rd.key = ol.relation_key
                    where ol.archived_at is null
                      and (ol.from_object_id = %s or ol.to_object_id = %s)
                    order by rd.sort_order, ol.created_at
                    """,
                    (object_id, object_id),
                )
                link_rows = cur.fetchall()

                if not link_rows:
                    return []

                # Collect all other object IDs to fetch their titles in one query
                other_ids = set()
                for row in link_rows:
                    other_id = row["to_object_id"] if row["from_object_id"] == object_id else row["from_object_id"]
                    other_ids.add(other_id)

                cur.execute(
                    "select object_id, type, title from linking.objects where object_id = any(%s)",
                    (list(other_ids),),
                )
                objects_by_id = {r["object_id"]: r for r in cur.fetchall()}

        # Build groups — keyed by (relation_key, label)
        groups: dict[tuple[str, str], LinkGroup] = {}

        for row in link_rows:
            is_forward = row["from_object_id"] == object_id
            label = row["forward_label"] if is_forward else row["reverse_label"]
            other_id = row["to_object_id"] if is_forward else row["from_object_id"]
            group_key = f"{row['relation_key']}__{'fwd' if is_forward else 'rev'}"

            other_obj = objects_by_id.get(other_id)
            item = LinkGroupItem(
                object_id = other_id,
                type      = other_obj["type"] if other_obj else "unknown",
                title     = other_obj["title"] if other_obj else None,
            )

            key = (group_key, label)
            if key not in groups:
                groups[key] = LinkGroup(group_key=group_key, label=label, items=[])
            groups[key].items.append(item)

        return list(groups.values())

    # ── Object search ─────────────────────────────────────────────────────────

    def search_objects(
        self,
        object_type: str,
        query: str,
        workspace_id: str | None,
        exclude_object_id: str | None,
        limit: int,
    ) -> list[ObjectRecord]:
        """ILIKE fuzzy search on linking.objects by title, filtered by type."""
        params: list = [object_type, f"%{query}%"]
        sql = """
            select object_id, workspace_id, type, title
            from linking.objects
            where type = %s
              and title ilike %s
        """
        if workspace_id is not None:
            sql += " and workspace_id = %s"
            params.append(workspace_id)
        if exclude_object_id is not None:
            sql += " and object_id != %s"
            params.append(exclude_object_id)
        sql += " order by title limit %s"
        params.append(limit)

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return [
            ObjectRecord(
                object_id    = r["object_id"],
                workspace_id = r["workspace_id"],
                type         = r["type"],
                title        = r["title"],
            )
            for r in rows
        ]

    # ── Query links ───────────────────────────────────────────────────────────

    def get_links(
        self,
        from_object_id: str | None,
        to_object_id: str | None,
        relation_key: str | None,
    ) -> list[LinkRecord]:
        """Query active links by from_object_id, to_object_id, or relation_key."""
        conditions = ["archived_at is null"]
        params: list = []

        if from_object_id:
            conditions.append("from_object_id = %s")
            params.append(from_object_id)
        if to_object_id:
            conditions.append("to_object_id = %s")
            params.append(to_object_id)
        if relation_key:
            conditions.append("relation_key = %s")
            params.append(relation_key)

        sql = (
            "select id, from_object_id, to_object_id, relation_key, "
            "created_by_type, created_by_id, confidence, archived_at, created_at "
            "from linking.object_links where "
            + " and ".join(conditions)
            + " order by created_at"
        )

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return [
            LinkRecord(
                link_id         = str(r["id"]),
                from_object_id  = r["from_object_id"],
                to_object_id    = r["to_object_id"],
                relation_key    = r["relation_key"],
                created_by_type = r["created_by_type"],
                created_by_id   = r["created_by_id"],
                confidence      = float(r["confidence"]),
                archived_at     = r["archived_at"].isoformat() if r["archived_at"] else None,
                created_at      = r["created_at"].isoformat(),
            )
            for r in rows
        ]

    # ── Soft-delete ───────────────────────────────────────────────────────────

    def archive_link(self, link_id: str) -> bool:
        """Set archived_at on link row. Return False if not found or already archived."""
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update linking.object_links
                    set archived_at = now()
                    where id = %s and archived_at is null
                    returning id
                    """,
                    (link_id,),
                )
                updated = cur.fetchone()
            conn.commit()
        return updated is not None

    # ── Relation definitions ──────────────────────────────────────────────────

    def get_relation_definitions(self, active_only: bool = True) -> list[RelationDefinition]:
        """Return relation definitions, ordered by sort_order."""
        sql = "select * from linking.relation_definitions"
        if active_only:
            sql += " where is_active = true"
        sql += " order by sort_order"

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

        return [
            RelationDefinition(
                key                = r["key"],
                forward_label      = r["forward_label"],
                reverse_label      = r["reverse_label"],
                is_directional     = r["is_directional"],
                allowed_from_types = list(r["allowed_from_types"]),
                allowed_to_types   = list(r["allowed_to_types"]),
                is_active          = r["is_active"],
                sort_order         = r["sort_order"],
            )
            for r in rows
        ]


# ── Private helpers ───────────────────────────────────────────────────────────

def _apply_canonical_direction(
    from_id: str,
    to_id: str,
    is_directional: bool,
) -> tuple[str, str]:
    """
    For non-directional relations: reorder IDs lexicographically so that
    the smaller UUID is always from_object_id, preventing mirror duplicates.
    For directional relations: return as-is (caller supplies source=child, target=parent).
    """
    if is_directional:
        return from_id, to_id
    if from_id <= to_id:
        return from_id, to_id
    return to_id, from_id


def _check_cycle(
    cur,
    from_id: str,
    to_id: str,
    relation_key: str,
    workspace_id: str | None,
) -> bool:
    """
    Check for direct reverse cycle only (v1 scope).
    Returns True if an active link (to_id -> from_id, relation_key) already exists.
    Full DAG cycle prevention deferred (design_review.md non_goals).
    """
    cur.execute(
        """
        select 1 from linking.object_links
        where from_object_id = %s
          and to_object_id   = %s
          and relation_key   = %s
          and archived_at is null
        limit 1
        """,
        (to_id, from_id, relation_key),
    )
    return cur.fetchone() is not None
