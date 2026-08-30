"""
EssayCards Sprint03_Images — HTTP-level pytest tests for the images router and
the import core:
  POST /api/essaycards/images/scan
  GET  /api/essaycards/images
  GET  /api/essaycards/images/{slug}

Scan scenarios run against a temporary staging directory and a temporary
images directory: the ``_tmp_dirs`` autouse fixture points
``backend.import_images.STAGING_DIR`` / ``IMAGES_DIR`` (which the router reads
at request time) at pytest ``tmp_path`` sub-directories, and small
Pillow-generated images are written into the tmp staging dir as input.

Test function names map 1:1 to the scenarios in Sprint03_Images/10_test_spec.md.
The ``skipped('error')`` reason path is left to manual/inspection coverage per
that spec's Scope section — it has no scenario here.

Fixture image rows (tests/fixtures.sql): fix-img-alpha (older, no file on disk)
and fix-img-beta (newer).
"""

import hashlib
import io
import re

import pytest
from PIL import Image

from backend import import_images

CACHE_CONTROL = "public, max-age=31536000, immutable"


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    images = tmp_path / "images"
    staging.mkdir()
    images.mkdir()
    monkeypatch.setattr(import_images, "STAGING_DIR", staging)
    monkeypatch.setattr(import_images, "IMAGES_DIR", images)
    return staging, images


# ── image builders ────────────────────────────────────────────────────────────

def _png_bytes(w: int, h: int, color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w: int, h: int, color=(200, 100, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _gif_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("P", (w, h)).save(buf, format="GIF")
    return buf.getvalue()


def _image_count(db_conn) -> int:
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.images")
        return cur.fetchone()["n"]


def _count_by_sha(db_conn, sha: str) -> int:
    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.images where source_sha256 = %s", (sha,))
        return cur.fetchone()["n"]


def _upload(client, data: bytes, filename: str = "pic.png", content_type: str = "image/png"):
    return client.post(
        "/api/essaycards/images/upload",
        files={"file": (filename, data, content_type)},
    )


# ── POST /images/scan ────────────────────────────────────────────────────────

def test_scan_imports_new_images_and_downscales_oversized(client, db_conn, _tmp_dirs):
    staging, images = _tmp_dirs
    (staging / "photo.png").write_bytes(_png_bytes(300, 200))
    (staging / "big.jpg").write_bytes(_jpeg_bytes(2500, 1200))

    r = client.post("/api/essaycards/images/scan")
    assert r.status_code == 200
    body = r.json()

    assert len(body["imported"]) == 2
    assert body["unchanged"] == 0
    assert body["skipped"] == []

    by_name = {i["source_filename"]: i for i in body["imported"]}
    assert set(by_name) == {"photo.png", "big.jpg"}
    for entry in body["imported"]:
        assert entry["url"] == f"/api/essaycards/images/{entry['slug']}"
        assert entry["byte_size"] > 0

    big = by_name["big.jpg"]
    assert big["width"] <= 2000 and big["height"] <= 2000
    assert max(big["width"], big["height"]) == 2000

    # A processed file and a matching row exist for each imported slug.
    for entry in body["imported"]:
        with db_conn.cursor() as cur:
            cur.execute(
                "select stored_filename from essaycards.images where slug = %s",
                (entry["slug"],),
            )
            row = cur.fetchone()
        assert row is not None
        assert (images / row["stored_filename"]).is_file()


def test_scan_is_idempotent_on_second_run(client, db_conn, _tmp_dirs):
    staging, images = _tmp_dirs
    (staging / "photo.png").write_bytes(_png_bytes(300, 200))
    (staging / "other.jpg").write_bytes(_jpeg_bytes(400, 300))

    first = client.post("/api/essaycards/images/scan")
    assert first.status_code == 200
    assert len(first.json()["imported"]) == 2

    count_after_first = _image_count(db_conn)
    files_after_first = sorted(p.name for p in images.iterdir())

    second = client.post("/api/essaycards/images/scan")
    assert second.status_code == 200
    body = second.json()
    assert body["imported"] == []
    assert body["unchanged"] == 2
    assert body["skipped"] == []

    assert _image_count(db_conn) == count_after_first
    assert sorted(p.name for p in images.iterdir()) == files_after_first


def test_scan_skips_non_image_file_and_continues(client, _tmp_dirs):
    staging, _images = _tmp_dirs
    (staging / "valid.png").write_bytes(_png_bytes(120, 90))
    (staging / "notes.txt").write_bytes(b"just some notes, not an image")

    r = client.post("/api/essaycards/images/scan")
    assert r.status_code == 200
    body = r.json()

    assert [i["source_filename"] for i in body["imported"]] == ["valid.png"]
    assert {"filename": "notes.txt", "reason": "not-an-image"} in body["skipped"]


def test_scan_skips_oversized_gif(client, db_conn, _tmp_dirs):
    staging, _images = _tmp_dirs
    # Longest edge > MAX_EDGE (2000) -> gif-too-large (animated-GIF resizing is
    # out of scope).
    (staging / "banner.gif").write_bytes(_gif_bytes(2500, 10))

    r = client.post("/api/essaycards/images/scan")
    assert r.status_code == 200
    body = r.json()

    assert body["imported"] == []
    assert {"filename": "banner.gif", "reason": "gif-too-large"} in body["skipped"]

    with db_conn.cursor() as cur:
        cur.execute("select count(*) as n from essaycards.images where source_filename = %s", ("banner.gif",))
        assert cur.fetchone()["n"] == 0


def test_scan_slug_collision_appends_hash_suffix(client, db_conn, _tmp_dirs):
    staging, images = _tmp_dirs
    # Same base name ("shot"), different bytes -> distinct slugs.
    (staging / "shot.PNG").write_bytes(_png_bytes(50, 50, color=(255, 0, 0)))
    (staging / "shot.png").write_bytes(_png_bytes(60, 60, color=(0, 0, 255)))

    r = client.post("/api/essaycards/images/scan")
    assert r.status_code == 200
    slugs = sorted(i["slug"] for i in r.json()["imported"])
    assert len(slugs) == 2

    assert "shot" in slugs
    other = next(s for s in slugs if s != "shot")
    assert re.fullmatch(r"shot-[0-9a-f]{6}", other)

    for slug in slugs:
        with db_conn.cursor() as cur:
            cur.execute("select stored_filename from essaycards.images where slug = %s", (slug,))
            row = cur.fetchone()
        assert row is not None
        assert (images / row["stored_filename"]).is_file()


def test_scan_infra_failure_returns_api_error(client, monkeypatch, tmp_path):
    monkeypatch.setattr(import_images, "STAGING_DIR", tmp_path / "does-not-exist")

    r = client.post("/api/essaycards/images/scan")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "IMPORT_INFRA_ERROR"
    assert "imported" not in body
    assert "skipped" not in body


# ── GET /images ──────────────────────────────────────────────────────────────

def test_list_images_returns_dataset_newest_first(client):
    r = client.get("/api/essaycards/images")
    assert r.status_code == 200
    body = r.json()

    assert body["meta"]["object_type"] == "image"
    slugs = [row["slug"] for row in body["rows"]]
    assert slugs.index("fix-img-beta") < slugs.index("fix-img-alpha")

    beta = next(row for row in body["rows"] if row["slug"] == "fix-img-beta")
    assert set(beta) == {
        "slug", "source_filename", "content_type", "byte_size",
        "width", "height", "created_at", "url",
    }
    assert beta["url"] == "/api/essaycards/images/fix-img-beta"
    assert "content" not in beta


def test_list_images_empty_is_valid(client, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("truncate essaycards.images")

    r = client.get("/api/essaycards/images")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == []
    assert body["meta"]["total"] == 0


# ── GET /images/{slug} ───────────────────────────────────────────────────────

def test_get_image_serves_bytes_with_immutable_cache(client, db_conn, _tmp_dirs):
    staging, images = _tmp_dirs
    (staging / "diagram.jpg").write_bytes(_jpeg_bytes(400, 300))

    scan = client.post("/api/essaycards/images/scan")
    slug = scan.json()["imported"][0]["slug"]

    with db_conn.cursor() as cur:
        cur.execute("select stored_filename from essaycards.images where slug = %s", (slug,))
        stored = cur.fetchone()["stored_filename"]
    expected = (images / stored).read_bytes()

    r = client.get(f"/api/essaycards/images/{slug}")
    assert r.status_code == 200
    assert r.content == expected
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == CACHE_CONTROL


def test_get_image_unknown_slug_returns_404(client):
    r = client.get("/api/essaycards/images/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_get_image_row_present_file_missing_returns_404(client):
    # fix-img-alpha has a fixture row but no file in the tmp images dir.
    r = client.get("/api/essaycards/images/fix-img-alpha")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── POST /images/upload (Sprint04_ImageUpload) ───────────────────────────────

def test_upload_valid_png_stores_processed_and_original(client, db_conn, _tmp_dirs):
    _staging, images = _tmp_dirs
    raw = _png_bytes(300, 200)
    sha = hashlib.sha256(raw).hexdigest()

    r = _upload(client, raw, filename="diagram.png")
    assert r.status_code == 200
    body = r.json()

    assert set(body) == {
        "slug", "source_filename", "url", "width", "height",
        "byte_size", "content_type", "created_at", "unchanged",
    }
    assert body["unchanged"] is False
    assert body["slug"] == "diagram"
    assert body["source_filename"] == "diagram.png"
    assert body["url"] == f"/api/essaycards/images/{body['slug']}"
    assert body["content_type"] == "image/png"
    assert body["width"] == 300 and body["height"] == 200
    assert body["byte_size"] > 0

    assert (images / f"{body['slug']}.png").is_file()
    assert (images / "originals" / f"{sha}.png").read_bytes() == raw
    assert _count_by_sha(db_conn, sha) == 1


def test_upload_bytes_matching_staged_image_is_unchanged(client, db_conn, _tmp_dirs):
    staging, images = _tmp_dirs
    raw = _png_bytes(320, 240)
    sha = hashlib.sha256(raw).hexdigest()
    (staging / "from-staging.png").write_bytes(raw)

    scan = client.post("/api/essaycards/images/scan")
    assert scan.status_code == 200
    assert len(scan.json()["imported"]) == 1
    files_after_scan = sorted(p.name for p in images.iterdir())

    r = _upload(client, raw, filename="from-staging.png")
    assert r.status_code == 200
    body = r.json()
    assert body["unchanged"] is True
    assert body["slug"] == "from-staging"

    assert _count_by_sha(db_conn, sha) == 1
    # No second processed file, and the raw bytes were NOT re-archived.
    assert sorted(p.name for p in images.iterdir()) == files_after_scan
    assert not (images / "originals" / f"{sha}.png").exists()


def test_upload_same_filename_collision_gets_hash_suffix(client, db_conn, _tmp_dirs):
    _staging, images = _tmp_dirs

    first = _upload(client, _png_bytes(40, 40, color=(255, 0, 0)), filename="dup.png")
    assert first.status_code == 200
    assert first.json()["slug"] == "dup"

    second = _upload(client, _png_bytes(50, 50, color=(0, 0, 255)), filename="dup.png")
    assert second.status_code == 200
    slug2 = second.json()["slug"]
    assert re.fullmatch(r"dup-[0-9a-f]{6}", slug2)

    for slug in ("dup", slug2):
        with db_conn.cursor() as cur:
            cur.execute("select stored_filename from essaycards.images where slug = %s", (slug,))
            row = cur.fetchone()
        assert row is not None
        assert (images / row["stored_filename"]).is_file()


def test_upload_non_image_returns_400(client, db_conn, _tmp_dirs):
    _staging, images = _tmp_dirs
    raw = b"not an image"
    sha = hashlib.sha256(raw).hexdigest()

    r = client.post(
        "/api/essaycards/images/upload",
        files={"file": ("notes.txt", raw, "application/octet-stream")},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["detail"]["reason"] == "not-an-image"

    assert _count_by_sha(db_conn, sha) == 0
    assert not (images / "originals").exists() or list((images / "originals").iterdir()) == []


def test_upload_svg_returns_400(client, db_conn):
    raw = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    sha = hashlib.sha256(raw).hexdigest()

    r = client.post(
        "/api/essaycards/images/upload",
        files={"file": ("logo.svg", raw, "image/svg+xml")},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert _count_by_sha(db_conn, sha) == 0


def test_upload_over_body_cap_returns_413(client, db_conn):
    before = _image_count(db_conn)
    oversized = b"\x00" * (13 * 1024 * 1024)

    r = client.post(
        "/api/essaycards/images/upload",
        files={"file": ("huge.bin", oversized, "application/octet-stream")},
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert _image_count(db_conn) == before


def test_upload_oversized_photo_downscaled_original_kept_full_size(client, db_conn, _tmp_dirs):
    _staging, images = _tmp_dirs
    raw = _jpeg_bytes(2600, 1300)
    sha = hashlib.sha256(raw).hexdigest()

    r = _upload(client, raw, filename="holiday.jpg", content_type="image/jpeg")
    assert r.status_code == 200
    body = r.json()

    assert body["unchanged"] is False
    assert body["width"] <= 2000 and body["height"] <= 2000
    assert max(body["width"], body["height"]) == 2000

    with db_conn.cursor() as cur:
        cur.execute("select stored_filename from essaycards.images where slug = %s", (body["slug"],))
        stored = cur.fetchone()["stored_filename"]
    with Image.open(images / stored) as processed:
        assert max(processed.size) == 2000

    original_path = images / "originals" / f"{sha}.jpg"
    assert original_path.read_bytes() == raw
    with Image.open(original_path) as original:
        assert original.size == (2600, 1300)


# [UI — manual] Paste an image onto the Images view -> it appears in the list
# with a Copy Markdown button. No Playwright infra in this component; verified
# manually, recorded as untested in the test report.
