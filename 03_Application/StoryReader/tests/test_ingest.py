"""
StoryReader — ingestion CLI/core tests.

Calls backend.ingest.upsert_story() directly against fixture markdown files
under tests/fixtures_md/ (no HTTP). Traceability: each function name maps to
a scenario in Sprint01_Core/10_test_spec.md.
"""

import os

from backend.ingest import IngestionError, upsert_story

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures_md")

# Fixture ids (tests/fixtures.sql)
LIGHTHOUSE_STORY_ID = "aa000001-0000-0000-0000-000000000001"
TIDEPOOL_STORY_ID   = "aa000002-0000-0000-0000-000000000002"
TIDEPOOL_V1_ANNOTATION_ID = "ac000004-0000-0000-0000-000000000004"


TIDEPOOL_BODY = (
    "The tide pool glimmered under the morning sun, holding a hundred small "
    "worlds in its shallow water.\n\nAnemones waved gently while hermit crabs "
    "shuffled between the rocks, unseen by anyone passing above.\n"
)


def _path(name: str) -> str:
    return os.path.join(FIXTURES_DIR, name)


def _write_md(tmp_path, slug: str, title: str, body: str) -> str:
    """Writes a fresh <slug>.md into tmp_path — the CLI's filename-derived-slug
    rule requires the filename to always match the front-matter slug, so a
    re-publish under a new body/title must still be named <slug>.md, same as
    Codex overwriting the same content_dir file on each publish.
    """
    path = os.path.join(tmp_path, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\ntitle: {title}\nslug: {slug}\n---\n{body}")
    return path


def _version_count(db_conn, story_id: str) -> int:
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from storyreader.story_versions where story_id = %s", (story_id,))
        return cur.fetchone()["n"]


# ── Ingestion — first publish creates version 1 ───────────────────────────────

def test_ingest_first_publish_creates_version_1(db_conn):
    result = upsert_story(db_conn, _path("harbor-lights.md"))

    assert result["action"] == "created"
    assert result["slug"] == "harbor-lights"
    assert result["version"] == 1
    assert result["story_id"]

    with db_conn.cursor() as cur:
        cur.execute("select latest_version from storyreader.stories where id = %s", (result["story_id"],))
        story = cur.fetchone()
        assert story["latest_version"] == 1

        cur.execute(
            "select version from storyreader.story_versions where story_id = %s",
            (result["story_id"],),
        )
        versions = cur.fetchall()
        assert len(versions) == 1
        assert versions[0]["version"] == 1


# ── Ingestion — unchanged content is a no-op ───────────────────────────────────

def test_ingest_unchanged_content_is_noop(db_conn):
    before = _version_count(db_conn, TIDEPOOL_STORY_ID)

    result1 = upsert_story(db_conn, _path("tidepool.md"))
    assert result1["action"] == "unchanged"
    assert _version_count(db_conn, TIDEPOOL_STORY_ID) == before

    result2 = upsert_story(db_conn, _path("tidepool.md"))
    assert result2["action"] == "unchanged"
    assert _version_count(db_conn, TIDEPOOL_STORY_ID) == before


# ── Ingestion — changed content appends a new version ─────────────────────────

def test_ingest_changed_content_appends_new_version(db_conn, tmp_path):
    changed_body = (
        "Storms had reshaped the tide pool overnight, scattering the anemones "
        "and hiding the hermit crabs deeper among the rocks.\n"
    )
    path = _write_md(tmp_path, "tidepool", "Tidepool", changed_body)
    result = upsert_story(db_conn, path)

    assert result["action"] == "new_version"
    assert result["version"] == 2

    with db_conn.cursor() as cur:
        cur.execute("select latest_version from storyreader.stories where id = %s", (TIDEPOOL_STORY_ID,))
        assert cur.fetchone()["latest_version"] == 2

        cur.execute(
            "select body_markdown from storyreader.story_versions where story_id = %s and version = 1",
            (TIDEPOOL_STORY_ID,),
        )
        v1 = cur.fetchone()
        assert "tide pool glimmered" in v1["body_markdown"]


# ── Ingestion — slug/filename mismatch is rejected ─────────────────────────────

def test_ingest_slug_filename_mismatch_rejected(db_conn):
    before_story_count = None
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from storyreader.stories")
        before_story_count = cur.fetchone()["n"]

    try:
        upsert_story(db_conn, _path("foo.md"))
        assert False, "expected IngestionError"
    except IngestionError:
        pass

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from storyreader.stories")
        assert cur.fetchone()["n"] == before_story_count


# ── Ingestion — re-ingestion can change title without a new version ───────────

def test_ingest_title_change_without_new_version(db_conn, tmp_path):
    before = _version_count(db_conn, TIDEPOOL_STORY_ID)

    path = _write_md(tmp_path, "tidepool", "Tidepool (Revised Notes)", TIDEPOOL_BODY)
    result = upsert_story(db_conn, path)

    assert result["action"] == "unchanged"
    assert _version_count(db_conn, TIDEPOOL_STORY_ID) == before

    with db_conn.cursor() as cur:
        cur.execute("select title from storyreader.stories where id = %s", (TIDEPOOL_STORY_ID,))
        assert cur.fetchone()["title"] == "Tidepool (Revised Notes)"


# ── Publishing a new version never touches existing annotations ───────────────

def test_publishing_new_version_never_touches_existing_annotations(db_conn, tmp_path):
    changed_body = (
        "Storms had reshaped the tide pool overnight, scattering the anemones "
        "and hiding the hermit crabs deeper among the rocks.\n"
    )
    path = _write_md(tmp_path, "tidepool", "Tidepool", changed_body)
    upsert_story(db_conn, path)

    with db_conn.cursor() as cur:
        cur.execute("select * from storyreader.annotations where id = %s", (TIDEPOOL_V1_ANNOTATION_ID,))
        ann = cur.fetchone()
        assert ann is not None
        assert ann["version"] == 1
        assert ann["selected_text"] == "The"

        cur.execute(
            "select count(*) as n from storyreader.annotations where story_id = %s and version = 2",
            (TIDEPOOL_STORY_ID,),
        )
        assert cur.fetchone()["n"] == 0
