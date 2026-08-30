"""
The images router: POST /images/scan, POST /images/upload, GET /images/{slug},
GET /images.

POST /images/upload (Sprint04) is the in-browser add-an-image path (paste /
drop / pick). It is a mutation endpoint (Dataset-exempt) that shares the exact
processing core with POST /images/scan — see ``backend.import_images
.process_image_bytes`` and the ``upload_image`` docstring below. It enforces a
hard 12 MiB request-body cap while reading and archives the raw uploaded bytes
under ``<images_dir>/originals/``.

GET /images/{slug} is a GET endpoint that returns raw image bytes via a plain
Starlette FileResponse — deliberately NOT a Dataset. This is an R-CON-BP-04
carve-out on the same rationale class as
GET /essays/{essay_id}/examination-package in backend/routers/examinations.py
(see that module's docstring): the response is a binary asset consumed as the
``src`` of an <img> tag rendered from Markdown, not UI-visible tabular data
rendered by a Dataset-consuming component. GET /images (the list) IS tabular
UI data and returns a proper Dataset per R-CON-BP-04.

POST /images/scan is a mutation endpoint (Dataset-exempt). It takes no request
body, is idempotent, and returns a typed report record on success (200). It
returns ApiError (code IMPORT_INFRA_ERROR, 500) ONLY when the staging
directory is unreadable or the images directory is unwritable — every per-file
image/format problem is a 'skipped' entry in the 200 report.

The served filesystem path for GET /images/{slug} is built from the
essaycards.images row's ``stored_filename``, never from the URL slug
(path-traversal guard, R-OPS-BP-02).
"""

import hashlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from backend import import_images
from backend.database import get_db
from backend.import_images import (
    ImportedImage,
    ImportInfraError,
    ImportReport,
    SkippedFile,
    process_image_bytes,
    scan_staging,
)
from platform_contracts import ColumnSchema, Dataset, DatasetMeta
from platform_errorhandling import api_error

router = APIRouter(prefix="/images", tags=["images"])

_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"

# Hard request-body cap for POST /images/upload (Sprint04 threat model,
# R-OPS-BP-02): the 5 MiB processed-output ceiling plus pre-downscale slack for
# a large phone photo. Enforced while reading — an oversized body is rejected
# before it is fully buffered.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
_UPLOAD_FALLBACK_NAME = "pasted-image"

IMAGE_SCHEMA: list[ColumnSchema] = [
    ColumnSchema(key="slug",            label="Slug",     type="string", sortable=False, filterable=False),
    ColumnSchema(key="source_filename", label="Filename", type="string", sortable=True,  filterable=True),
    ColumnSchema(key="content_type",    label="Type",     type="string", sortable=False, filterable=True),
    ColumnSchema(key="byte_size",       label="Size",     type="number", sortable=True,  filterable=False),
    ColumnSchema(key="width",           label="Width",    type="number", sortable=False, filterable=False),
    ColumnSchema(key="height",          label="Height",   type="number", sortable=False, filterable=False),
    ColumnSchema(key="created_at",      label="Imported", type="date",   sortable=True,  filterable=False),
    ColumnSchema(key="url",             label="URL",      type="string", sortable=False, filterable=False),
]


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat()
    d["url"] = f"/api/essaycards/images/{d['slug']}"
    return d


def _report_to_json(report: ImportReport) -> dict[str, Any]:
    return {
        "imported": [
            {
                "slug": i.slug,
                "source_filename": i.source_filename,
                "url": f"/api/essaycards/images/{i.slug}",
                "width": i.width,
                "height": i.height,
                "byte_size": i.byte_size,
            }
            for i in report.imported
        ],
        "unchanged": report.unchanged,
        "skipped": [{"filename": s.filename, "reason": s.reason} for s in report.skipped],
    }


def _upload_record(
    *,
    slug: str,
    source_filename: str,
    width: int | None,
    height: int | None,
    byte_size: int,
    content_type: str,
    created_at: str,
    unchanged: bool,
) -> dict[str, Any]:
    """The typed single-image record returned by POST /images/upload (200)."""
    return {
        "slug": slug,
        "source_filename": source_filename,
        "url": f"/api/essaycards/images/{slug}",
        "width": width,
        "height": height,
        "byte_size": byte_size,
        "content_type": content_type,
        "created_at": created_at,
        "unchanged": unchanged,
    }


def _dataset_response(dataset: Dataset) -> JSONResponse:
    return JSONResponse(content=dataset.model_dump(by_alias=True, mode="json"))


@router.post("/scan", response_model=None)
def scan_images() -> JSONResponse:
    """Run the staging import core once. No request body. Idempotent.

    200: typed report record { imported: [...], unchanged: int, skipped: [...] }.
    500 ApiError IMPORT_INFRA_ERROR: staging dir unreadable / images dir
    unwritable. Per-file problems are 'skipped' entries in the 200 body.
    """
    try:
        with get_db() as conn:
            report = scan_staging(conn, import_images.STAGING_DIR, import_images.IMAGES_DIR)
    except ImportInfraError as exc:
        return api_error("IMPORT_INFRA_ERROR", str(exc), status=500)
    return JSONResponse(content=_report_to_json(report))


@router.post("/upload", response_model=None)
async def upload_image(request: Request) -> JSONResponse:
    """Import one image supplied as multipart/form-data — the in-browser
    paste / drop / pick path. Runs the SAME core as POST /images/scan
    (``process_image_bytes``): decode + exif_transpose + Lanczos downscale +
    metadata-stripped re-encode + slug + source_sha256 idempotency + per-file
    transaction. The raw uploaded bytes are archived to
    ``<images_dir>/originals/<source_sha256><ext>`` before the import.

    Fields: ``file`` (required, the image); ``filename`` (optional, overrides
    the multipart part filename). Effective filename:
    ``filename`` field -> part filename -> ``pasted-image``.

    Mutation endpoint — R-CON-BP-04 Dataset-exempt.
      200: { slug, source_filename, url, width, height, byte_size,
             content_type, created_at, unchanged }. ``unchanged`` is true when
             the sha was already imported (via staging or a prior upload);
             ``slug`` then points at the existing row and nothing is written.
      413 ApiError PAYLOAD_TOO_LARGE: body over the 12 MiB cap (rejected while
             reading, before the whole body is buffered).
      400 ApiError VALIDATION_ERROR: not a decodable image of an allowed raster
             format / SVG / format mismatch. ``detail.reason`` is from the
             Sprint03 skip vocabulary ('not-an-image' | 'format-mismatch').
      500 ApiError IMPORT_INFRA_ERROR: images dir or originals/ unwritable, or
             a connection-level DB failure.
    """
    too_large = api_error(
        "PAYLOAD_TOO_LARGE",
        f"Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB limit",
        status=413,
    )

    # Cheap pre-check: reject an oversized declared body before reading it.
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MAX_UPLOAD_BYTES:
                return too_large
        except ValueError:
            pass

    # Buffer the raw body with a running cap — never slurp an unbounded stream.
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > MAX_UPLOAD_BYTES:
            return too_large

    # Parse the multipart form from the capped buffer (reuses Starlette's
    # parser without re-exposing the unbounded request stream).
    async def _receive() -> dict[str, Any]:
        return {"type": "http.request", "body": bytes(buf), "more_body": False}

    form = await Request(request.scope, _receive).form(max_part_size=MAX_UPLOAD_BYTES)
    try:
        file_part = form.get("file")
        if file_part is None or not hasattr(file_part, "read"):
            return api_error(
                "VALIDATION_ERROR", "Missing 'file' upload part",
                {"reason": "not-an-image"}, status=400,
            )
        raw = await file_part.read()
        part_name = getattr(file_part, "filename", None)
        name_field = form.get("filename")
    finally:
        await form.close()

    override = name_field.strip() if isinstance(name_field, str) and name_field.strip() else None
    effective_name = override or (part_name or "").strip() or _UPLOAD_FALLBACK_NAME

    if not raw:
        return api_error(
            "VALIDATION_ERROR", "Uploaded file is empty",
            {"reason": "not-an-image"}, status=400,
        )

    # SVG served same-origin is a stored-XSS vector — reject before processing
    # (Pillow could not decode it anyway; this makes the rejection explicit).
    sniff = raw[:1024].lstrip().lower()
    if (
        effective_name.lower().endswith(".svg")
        or sniff.startswith(b"<svg")
        or (sniff.startswith(b"<?xml") and b"<svg" in sniff)
    ):
        return api_error(
            "VALIDATION_ERROR", "SVG images are not accepted",
            {"reason": "format-mismatch"}, status=400,
        )

    originals_dir = Path(import_images.IMAGES_DIR) / "originals"
    try:
        with get_db() as conn:
            result = process_image_bytes(
                conn,
                source_filename=effective_name,
                raw=bytes(raw),
                images_dir=Path(import_images.IMAGES_DIR),
                save_original_dir=originals_dir,
            )
            # Clear the idempotency-probe read tx; an imported row is already
            # committed inside the core (mirrors scan_staging).
            conn.rollback()
    except ImportInfraError as exc:
        return api_error("IMPORT_INFRA_ERROR", str(exc), status=500)

    if isinstance(result, SkippedFile):
        return api_error(
            "VALIDATION_ERROR",
            f"File is not an importable image ({result.reason})",
            {"reason": result.reason}, status=400,
        )

    if result == "unchanged":
        source_sha256 = hashlib.sha256(bytes(raw)).hexdigest()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select slug, source_filename, content_type, byte_size,
                           width, height, created_at
                    from essaycards.images
                    where source_sha256 = %s
                    """,
                    (source_sha256,),
                )
                row = cur.fetchone()
            conn.rollback()
        return JSONResponse(content=_upload_record(
            slug=row["slug"],
            source_filename=row["source_filename"],
            width=row["width"],
            height=row["height"],
            byte_size=row["byte_size"],
            content_type=row["content_type"],
            created_at=row["created_at"].isoformat(),
            unchanged=True,
        ))

    assert isinstance(result, ImportedImage)
    return JSONResponse(content=_upload_record(
        slug=result.slug,
        source_filename=result.source_filename,
        width=result.width,
        height=result.height,
        byte_size=result.byte_size,
        content_type=result.content_type,
        created_at=result.created_at,
        unchanged=False,
    ))


@router.get("", response_model=None)
def list_images() -> JSONResponse:
    """No parameters. Ordered created_at desc (newest imported first). Empty
    result is valid. The response never includes image bytes — metadata plus a
    computed url only."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select slug, source_filename, content_type, byte_size, width, height, created_at
                from essaycards.images
                order by created_at desc
                """
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]

    dataset = Dataset(
        meta=DatasetMeta(
            object_type="image",
            label="Images",
            total=len(rows),
            page=1,
            page_size=max(len(rows), 1),
            row_actions=[],
        ),
        **{"schema": IMAGE_SCHEMA},
        rows=rows,
    )
    return _dataset_response(dataset)


@router.get("/{slug}", response_model=None)
def get_image(slug: str):
    """Serve the processed image file for a slug, for use as the src of an
    <img> tag. 404 ApiError NOT_FOUND (never 500) if the slug has no row, or
    the row exists but its file is missing on disk. The served path is built
    from the row's stored_filename, never from the URL slug."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select stored_filename, content_type from essaycards.images where slug = %s",
                (slug,),
            )
            row = cur.fetchone()

    if row is None:
        return api_error("NOT_FOUND", f"Image '{slug}' not found", status=404)

    path = Path(import_images.IMAGES_DIR) / row["stored_filename"]
    if not path.is_file():
        return api_error("NOT_FOUND", f"Image '{slug}' file is missing", status=404)

    return FileResponse(
        path,
        media_type=row["content_type"],
        headers={"Cache-Control": _IMMUTABLE_CACHE},
    )
