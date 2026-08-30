"""
Image import — a bytes-first per-image core (process_image_bytes) shared by
scan_staging (server staging folder) and POST /api/essaycards/images/upload
(in-browser paste / drop / pick), plus a ``python -m backend.import_images``
CLI wrapper, structured like backend/ingest.py.

Flow (10_architecture.json internal_flow steps 10 and 14):
  - list ``staging_dir`` non-recursively; a whole-directory failure (staging
    unreadable / images dir unwritable) raises ImportInfraError.
  - per file:
      (a) extension not in ACCEPT_EXTS            -> SkippedFile('not-an-image')
      (b) hash the ORIGINAL bytes (source_sha256, the idempotency key); a row
          with that hash already present           -> unchanged
      (c) Pillow decode failure                    -> SkippedFile('not-an-image')
          declared extension disagrees with format -> SkippedFile('format-mismatch')
      (d) ImageOps.exif_transpose; Lanczos downscale if max(dim) > MAX_EDGE
          (never upscale); re-encode dropping all metadata. GIF is passed
          through byte-for-byte only if byte_size <= MAX_BYTES and
          max(dim) <= MAX_EDGE, else SkippedFile('gif-too-large'). A result
          still larger than MAX_BYTES                -> SkippedFile('too-large')
      (e) derive the slug from the basename; on collision with a row that has
          a different source_sha256, append '-' + first 6 hex of the new hash
      (f) inside a per-file SAVEPOINT: write images_dir/<slug>.<ext>, INSERT
          the essaycards.images row, RELEASE the SAVEPOINT and commit that row
          before the next file. An INSERT failure is ROLLBACK-TO-SAVEPOINT'd
          (psycopg2 would otherwise leave the whole transaction aborted), the
          just-written file is unlinked, and the file is recorded as
          SkippedFile('error') so the batch continues. Already-committed rows
          from earlier files in the same scan stay committed and are visible
          to _resolve_slug for later files. Only a connection-level failure
          (OperationalError / InterfaceError) is re-raised, as ImportInfraError.

MAX_EDGE / JPEG_QUALITY / MAX_BYTES are module-level constants here, NOT
config.env entries. MAX_BYTES is one decision shared with the
ck_images_byte_size CHECK in schema.sql — the two must change together.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extensions
from PIL import Image, ImageOps

# ── Module constants ────────────────────────────────────────────────────────────

STAGING_DIR = Path("/app/staging")   # read-only staging mount
IMAGES_DIR = Path("/app/images")     # app-writable processed-output mount

MAX_EDGE = 2000                      # px; downscale (Lanczos) above this, never upscale
JPEG_QUALITY = 82                    # progressive JPEG / WebP re-encode quality
MAX_BYTES = 5 * 1024 * 1024          # hard ceiling on a processed file (== schema CHECK)

ACCEPT_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Pillow format name -> (content_type, output extension) for the re-encoded file.
_FORMAT_META = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG":  ("image/png", ".png"),
    "GIF":  ("image/gif", ".gif"),
    "WEBP": ("image/webp", ".webp"),
}

# Which sniffed Pillow formats a given staged-file extension is allowed to be.
_EXT_TO_FORMATS = {
    ".jpg":  {"JPEG"},
    ".jpeg": {"JPEG"},
    ".png":  {"PNG"},
    ".gif":  {"GIF"},
    ".webp": {"WEBP"},
}

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


# ── Public data model ─────────────────────────────────────────────────────────

class ImportInfraError(Exception):
    """Raised when the staging directory is unreadable or the images directory
    is unwritable, or on a connection-level database failure during import.
    Mapped by the endpoint to a 500 ApiError (code IMPORT_INFRA_ERROR). Never
    raised for a per-file image problem — those become SkippedFile entries."""


@dataclass
class ImportedImage:
    slug:            str
    source_filename: str
    width:           int | None
    height:          int | None
    byte_size:       int
    content_type:    str
    stored_filename: str
    created_at:      str = ""      # ISO-8601, from INSERT ... returning created_at


@dataclass
class SkippedFile:
    filename: str
    reason:   str  # 'not-an-image' | 'format-mismatch' | 'gif-too-large' | 'too-large' | 'error'


@dataclass
class ImportReport:
    imported:  list[ImportedImage] = field(default_factory=list)
    unchanged: int = 0
    skipped:   list[SkippedFile] = field(default_factory=list)


# ── Shared core ──────────────────────────────────────────────────────────────

def scan_staging(conn: Any, staging_dir: Path = STAGING_DIR, images_dir: Path = IMAGES_DIR) -> ImportReport:
    """Import every not-yet-seen file in ``staging_dir`` into a web-ready asset
    under ``images_dir`` plus an essaycards.images row. Idempotent (keyed on
    source_sha256). Commits each imported row under its own SAVEPOINT so one
    file's INSERT failure neither aborts the batch nor rolls back the rows
    already imported in this scan. Raises ImportInfraError only on a
    whole-directory or connection-level failure."""
    staging_dir = Path(staging_dir)
    images_dir = Path(images_dir)

    try:
        entries = sorted(p for p in staging_dir.iterdir() if p.is_file())
    except OSError as exc:
        raise ImportInfraError(f"staging directory {staging_dir} is not readable: {exc}") from exc

    try:
        images_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ImportInfraError(f"images directory {images_dir} is not writable: {exc}") from exc
    if not os.access(images_dir, os.W_OK):
        raise ImportInfraError(f"images directory {images_dir} is not writable")

    report = ImportReport()
    for entry in entries:
        # Staging keeps the filename-extension gate (a misnamed file is
        # 'not-an-image' without a decode attempt); the bytes core sniffs the
        # real format for everything that passes it.
        if entry.suffix.lower() not in ACCEPT_EXTS:
            report.skipped.append(SkippedFile(filename=entry.name, reason="not-an-image"))
            continue

        result = process_image_bytes(
            conn,
            source_filename=entry.name,
            raw=entry.read_bytes(),
            images_dir=images_dir,
            save_original_dir=None,   # the staging file itself is the retained original
        )
        if isinstance(result, ImportedImage):
            report.imported.append(result)
        elif result == "unchanged":
            report.unchanged += 1
        else:  # SkippedFile
            report.skipped.append(result)

    # Every imported row was already committed inside process_image_bytes. The
    # idempotency probes (and a trailing skipped/unchanged file) can still leave
    # a read-only transaction open on the pooled connection; clear it so the
    # connection is returned clean, mirroring backend/ingest.upsert_document.
    conn.rollback()
    return report


# ── Private helpers ─────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slugify(basename: str) -> str:
    """basename -> lowercase, drop extension, collapse every non-[a-z0-9] run to
    a single '-', trim leading/trailing '-'. Empty result -> 'image'."""
    stem = Path(basename).stem.lower()
    slug = _SLUG_STRIP_RE.sub("-", stem).strip("-")
    return slug or "image"


def _resolve_slug(cur: Any, base_slug: str, source_sha256: str) -> str:
    """Return ``base_slug``, or ``base_slug`` + '-' + first 6 hex of
    ``source_sha256`` if ``base_slug`` is already taken by a row with a
    different source_sha256."""
    cur.execute("select source_sha256 from essaycards.images where slug = %s", (base_slug,))
    row = cur.fetchone()
    if row is None or row["source_sha256"] == source_sha256:
        return base_slug
    return f"{base_slug}-{source_sha256[:6]}"


def _process_image(data: bytes, ext: str | None = None):
    """Decode, validate, normalize and re-encode one image from bytes.

    ``ext`` (a declared filename extension, staging path only) is cross-checked
    against the sniffed Pillow format; pass ``None`` for the bytes/upload path,
    where there is no trusted extension to disagree with.

    Returns ``(processed_bytes, content_type, out_ext, width, height)`` on
    success, or a skip-reason string
    ('not-an-image' | 'format-mismatch' | 'gif-too-large' | 'too-large')."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return "not-an-image"

    fmt = (img.format or "").upper()
    if fmt not in _FORMAT_META:
        return "not-an-image"
    if ext is not None and fmt not in _EXT_TO_FORMATS.get(ext, set()):
        return "format-mismatch"

    if fmt == "GIF":
        # Animated-GIF resizing is out of scope: pass the original bytes
        # through unchanged, but only within the size/edge ceiling.
        w, h = img.size
        if len(data) > MAX_BYTES or max(w, h) > MAX_EDGE:
            return "gif-too-large"
        return data, "image/gif", ".gif", w, h

    img = ImageOps.exif_transpose(img)
    w, h = img.size
    if max(w, h) > MAX_EDGE:
        scale = MAX_EDGE / max(w, h)
        img = img.resize(
            (max(1, round(w * scale)), max(1, round(h * scale))),
            Image.Resampling.LANCZOS,
        )
        w, h = img.size

    buf = io.BytesIO()
    # Explicit empty exif/icc_profile so no source metadata survives the re-encode.
    save_kwargs = {"exif": b"", "icc_profile": b""}
    if fmt == "JPEG":
        out = img if img.mode in ("RGB", "L") else img.convert("RGB")
        out.save(buf, format="JPEG", quality=JPEG_QUALITY, progressive=True, optimize=True, **save_kwargs)
        content_type, out_ext = "image/jpeg", ".jpg"
    elif fmt == "PNG":
        img.save(buf, format="PNG", optimize=True, **save_kwargs)
        content_type, out_ext = "image/png", ".png"
    else:  # WEBP
        out = img if img.mode in ("RGB", "RGBA", "L") else img.convert("RGBA")
        out.save(buf, format="WEBP", quality=JPEG_QUALITY, method=6, **save_kwargs)
        content_type, out_ext = "image/webp", ".webp"

    processed = buf.getvalue()
    if len(processed) > MAX_BYTES:
        return "too-large"
    return processed, content_type, out_ext, w, h


def _ensure_in_transaction(conn: Any, cur: Any) -> None:
    """Open an explicit transaction if none is active.

    The per-file work below issues ``SAVEPOINT``, which Postgres rejects
    ("SAVEPOINT can only be used in transaction blocks") unless a transaction
    is already open. psycopg2 with ``autocommit == False`` normally opens one
    implicitly on the first statement, but under the ASGI request path
    (FastAPI runs this sync code via ``run_in_threadpool``) the pooled
    connection has been observed still IDLE here — and each successful file's
    ``conn.commit()`` closes the transaction, so the next file would hit the
    same gap. Guarding on ``transaction_status`` keeps this a no-op whenever a
    transaction is already active.
    """
    if conn.info.transaction_status == psycopg2.extensions.TRANSACTION_STATUS_IDLE:
        cur.execute("begin")


def process_image_bytes(
    conn: Any,
    *,
    source_filename: str,
    raw: bytes,
    images_dir: Path,
    save_original_dir: Path | None = None,
) -> "ImportedImage | str | SkippedFile":
    """Bytes-first per-image import core, shared by scan_staging (staged files)
    and POST /images/upload (HTTP uploads).

    Returns:
      - ImportedImage           on a successful new import (row committed).
      - the string "unchanged"  when a row with this source_sha256 already
                                exists — no file is (re)written, no INSERT.
      - SkippedFile             for a per-image problem ('not-an-image' |
                                'format-mismatch' | 'gif-too-large' |
                                'too-large' | 'error').

    Raises ImportInfraError on an unwritable images / originals directory or a
    connection-level database failure — never for a per-image problem.

    ``save_original_dir``: when not None, the raw bytes are archived to
    ``save_original_dir/<source_sha256><ext>`` (ext from the sniffed format)
    before the import transaction. scan_staging passes None — the staging file
    itself is the retained original.

    Preserves Sprint03's per-file boundary: ``_ensure_in_transaction`` guard,
    ``SAVEPOINT`` -> write file -> INSERT -> ``RELEASE`` + ``conn.commit()``;
    on INSERT failure ``ROLLBACK TO SAVEPOINT``, unlink the processed file
    (the original in ``save_original_dir`` is left in place), return
    SkippedFile('error')."""
    images_dir = Path(images_dir)
    source_sha256 = _sha256(raw)

    try:
        with conn.cursor() as cur:
            cur.execute(
                "select 1 from essaycards.images where source_sha256 = %s",
                (source_sha256,),
            )
            if cur.fetchone() is not None:
                return "unchanged"

            result = _process_image(raw)
            if isinstance(result, str):
                return SkippedFile(filename=source_filename, reason=result)
            processed, content_type, out_ext, width, height = result

            if save_original_dir is not None:
                save_original_dir = Path(save_original_dir)
                try:
                    save_original_dir.mkdir(parents=True, exist_ok=True)
                    (save_original_dir / f"{source_sha256}{out_ext}").write_bytes(raw)
                except OSError as exc:
                    raise ImportInfraError(
                        f"originals directory {save_original_dir} is not writable: {exc}"
                    ) from exc

            base_slug = _slugify(source_filename)

            _ensure_in_transaction(conn, cur)
            cur.execute("savepoint import_one")
            slug = _resolve_slug(cur, base_slug, source_sha256)
            stored_filename = f"{slug}{out_ext}"
            dest = images_dir / stored_filename
            try:
                images_dir.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(processed)
            except OSError as exc:
                cur.execute("rollback to savepoint import_one")
                raise ImportInfraError(
                    f"images directory {images_dir} is not writable: {exc}"
                ) from exc

            try:
                cur.execute(
                    """
                    insert into essaycards.images
                        (slug, stored_filename, content_type, byte_size, width, height,
                         source_sha256, source_filename)
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    returning created_at
                    """,
                    (slug, stored_filename, content_type, len(processed), width, height,
                     source_sha256, source_filename),
                )
                created_at = cur.fetchone()["created_at"]
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                raise
            except Exception:
                cur.execute("rollback to savepoint import_one")
                try:
                    dest.unlink()
                except OSError:
                    pass
                return SkippedFile(filename=source_filename, reason="error")

            cur.execute("release savepoint import_one")
            conn.commit()
            return ImportedImage(
                slug=slug,
                source_filename=source_filename,
                width=width,
                height=height,
                byte_size=len(processed),
                content_type=content_type,
                stored_filename=stored_filename,
                created_at=created_at.isoformat(),
            )
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
        raise ImportInfraError(
            f"database connection failure during import: {exc}"
        ) from exc


# ── CLI wrapper ─────────────────────────────────────────────────────────────

def _main() -> None:
    import sys

    from backend.database import get_db, init_pool

    init_pool()
    try:
        with get_db() as conn:
            report = scan_staging(conn, STAGING_DIR, IMAGES_DIR)
    except ImportInfraError as exc:
        print(f"Image import failed: {exc}", file=sys.stderr)
        sys.exit(1)

    for img in report.imported:
        print(f"imported {img.source_filename} -> {img.slug} "
              f"({img.width}x{img.height}, {img.byte_size} bytes)")
    print(f"unchanged: {report.unchanged}")
    for skipped in report.skipped:
        print(f"skipped {skipped.filename}: {skipped.reason}")


if __name__ == "__main__":
    _main()
