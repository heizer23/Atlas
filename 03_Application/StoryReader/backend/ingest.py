"""
One-shot markdown ingestion — importable core (upsert_story) plus a
`python -m backend.ingest <path>` CLI entrypoint. The only way story content
enters this app (10_architecture.json §internal_flow step 2).

Usage (from Codex's SSH session, over docker exec):
    docker exec atlas-storyreader python -m backend.ingest content/<slug>.md

Grammar:
  - YAML front matter delimited by a leading '---' line and the next '---'
    line; requires non-empty 'title' and 'slug'.
  - The front-matter 'slug' must exactly equal the filename-derived slug
    (the CLI argument's basename with '.md' stripped) — a mismatch aborts
    ingestion before any database write.
  - Everything after the closing '---' line is body_markdown, stored
    verbatim (immutable once inserted).

Idempotency: content_sha256 = sha256(body_markdown after front matter is
stripped), compared against the story's CURRENT latest version only.
Unchanged -> no-op (title may still be updated). Changed -> a new,
append-only story_versions row is inserted; the existing latest version's
row is never touched.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Any

import yaml

# ── Public API ────────────────────────────────────────────────────────────

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n?", re.DOTALL)


class IngestionError(Exception):
    """Raised for any parse/validation failure before a database write is attempted."""


def _parse_front_matter(raw_text: str) -> tuple[dict[str, Any], str]:
    """Splits the leading '---' YAML block from the markdown body.

    Returns (front_matter_fields, body_markdown). Raises IngestionError on
    missing/unparsable front matter.
    """
    m = _FRONT_MATTER_RE.match(raw_text)
    if not m:
        raise IngestionError(
            "Missing or unparsable YAML front matter — file must start with '---' "
            "and the front matter block must be closed with a second '---' line"
        )
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise IngestionError(f"Front matter is not valid YAML: {exc}") from exc

    if not isinstance(fm, dict):
        raise IngestionError("Front matter must be a YAML mapping")

    return fm, raw_text[m.end():]


def upsert_story(conn: Any, file_path: str) -> dict[str, Any]:
    """Reads the file at file_path (relative to /app), validates it, and
    upserts storyreader.stories / storyreader.story_versions per the
    Content Publishing rules in 00_draft.md / 10_architecture.json
    §internal_flow step 2.

    Raises IngestionError on any validation failure — never partially
    writes (all validation happens before the first INSERT/UPDATE). Does
    not commit or rollback itself — the caller (main(), or a test using
    backend.database.get_db()) owns the transaction boundary.

    Returns {"action": "created"|"unchanged"|"new_version", "slug",
    "story_id", "version"}.
    """
    if not os.path.isfile(file_path):
        raise IngestionError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    fm, body_markdown = _parse_front_matter(raw_text)

    title = fm.get("title")
    slug = fm.get("slug")
    if not isinstance(title, str) or not title.strip():
        raise IngestionError("Front matter missing required non-empty 'title'")
    if not isinstance(slug, str) or not slug.strip():
        raise IngestionError("Front matter missing required non-empty 'slug'")
    title = title.strip()
    slug = slug.strip()

    filename = os.path.basename(file_path)
    if not filename.endswith(".md"):
        raise IngestionError(f"File must have a .md extension: {file_path}")
    filename_slug = filename[: -len(".md")]
    if slug != filename_slug:
        raise IngestionError(
            f"Front matter slug '{slug}' does not match filename-derived slug "
            f"'{filename_slug}' — a slug is never changed by re-ingestion; rename "
            "the file or fix the front matter"
        )

    content_sha256 = hashlib.sha256(body_markdown.encode("utf-8")).hexdigest()

    with conn.cursor() as cur:
        cur.execute(
            "select id, latest_version from storyreader.stories where slug = %s",
            (slug,),
        )
        story = cur.fetchone()

        if story is None:
            cur.execute(
                """
                insert into storyreader.stories (slug, title, latest_version)
                values (%s, %s, 1)
                returning id
                """,
                (slug, title),
            )
            story_id = cur.fetchone()["id"]
            cur.execute(
                """
                insert into storyreader.story_versions
                    (story_id, version, body_markdown, content_sha256)
                values (%s, 1, %s, %s)
                """,
                (story_id, body_markdown, content_sha256),
            )
            conn.commit()
            return {"action": "created", "slug": slug, "story_id": str(story_id), "version": 1}

        story_id = story["id"]
        latest_version = story["latest_version"]

        cur.execute(
            """
            select content_sha256 from storyreader.story_versions
            where story_id = %s and version = %s
            """,
            (story_id, latest_version),
        )
        current = cur.fetchone()
        current_sha = current["content_sha256"] if current else None

        if current_sha == content_sha256:
            cur.execute(
                "update storyreader.stories set title = %s, updated_at = now() where id = %s and title <> %s",
                (title, story_id, title),
            )
            conn.commit()
            return {"action": "unchanged", "slug": slug, "story_id": str(story_id), "version": latest_version}

        new_version = latest_version + 1
        cur.execute(
            """
            insert into storyreader.story_versions
                (story_id, version, body_markdown, content_sha256)
            values (%s, %s, %s, %s)
            """,
            (story_id, new_version, body_markdown, content_sha256),
        )
        cur.execute(
            "update storyreader.stories set latest_version = %s, title = %s, updated_at = now() where id = %s",
            (new_version, title, story_id),
        )
        conn.commit()
        return {"action": "new_version", "slug": slug, "story_id": str(story_id), "version": new_version}


# ── CLI entrypoint ────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python -m backend.ingest <path>", file=sys.stderr)
        return 2

    path = argv[1]

    from backend.database import get_db, init_pool

    init_pool()
    try:
        with get_db() as conn:
            result = upsert_story(conn, path)
    except IngestionError as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
