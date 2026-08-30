# Test Spec — EssayCards — Sprint03_Images

## Scope
Covers the new image import pipeline and its three endpoints (`POST /api/essaycards/images/scan`,
`GET /api/essaycards/images/{slug}`, `GET /api/essaycards/images`) plus the review-card Markdown
image rendering. Out of scope: the markdown/JSON ingestion paths, the due-queue/review scheduling,
and the oral-examinations endpoints (all unchanged this sprint and covered by their existing tests).

Scan-based scenarios run against a temporary staging directory and a temporary images directory
(the module-level `STAGING_DIR` / `IMAGES_DIR` and the images router's directory reference are
pointed at `tmp_path`), with small generated images used as staged input.

The scan report's `skipped[].reason` is one of exactly `not-an-image`, `format-mismatch`,
`gif-too-large`, `too-large`, or `error` (a per-file INSERT failure rolled back to that file's
savepoint). This is the same set enumerated in `10_architecture.json` and `10_scaffolding.json`.
The `error` reason path (a per-file INSERT failure that is rolled back to the file's savepoint
so the batch continues) is deliberately left to manual/inspection coverage this sprint — it has
no dedicated automated scenario below. The other four reasons each have a scan scenario.

## Scenarios

### Scan imports new staged images
- **Given:** an empty images directory and a staging directory containing two valid images — one in-bounds PNG and one JPEG whose longest edge is greater than 2000 px.
- **When:** `POST /api/essaycards/images/scan` is called with no body.
- **Then:** the response is `200` with `imported` listing two entries (each with `slug`, `source_filename`, `url`, `width`, `height`, `byte_size`), `unchanged` is `0`, and `skipped` is empty; the oversized image's stored `width` and `height` are both `<= 2000`; a processed file now exists in the images directory for each imported slug and a matching `essaycards.images` row exists.

### Scan is idempotent on a second run
- **Given:** a staging directory whose images were already imported by a prior scan, with no files added or removed.
- **When:** `POST /api/essaycards/images/scan` is called again.
- **Then:** the response is `200` with `imported` empty, `unchanged` equal to the number of staged files, and `skipped` empty; no new `essaycards.images` rows and no new files are created.

### Scan skips a non-image file and keeps going
- **Given:** a staging directory containing one valid image and a file named `notes.txt`.
- **When:** `POST /api/essaycards/images/scan` is called.
- **Then:** the response is `200`; the valid image appears in `imported`; `skipped` contains an entry `{ filename: "notes.txt", reason: "not-an-image" }`; the scan is not aborted by the non-image file.

### Scan skips an oversized GIF
- **Given:** a staging directory containing a `.gif` whose byte size exceeds 5 MiB (or whose longest edge exceeds 2000 px).
- **When:** `POST /api/essaycards/images/scan` is called.
- **Then:** the response is `200`; the GIF appears in `skipped` with `reason: "gif-too-large"`; no row or file is created for it.

### Scan resolves a slug collision
- **Given:** a staging directory containing two different images that share the same base filename (e.g. `IMG_1234 (1).JPG` and `IMG_1234 (1).png` with different bytes).
- **When:** `POST /api/essaycards/images/scan` is called.
- **Then:** both are imported with distinct slugs; the second slug is the first slug followed by `-` and six hexadecimal characters; both processed files exist and both rows exist.

### Scan infrastructure failure returns an ApiError
- **Given:** the staging directory path does not exist or cannot be read.
- **When:** `POST /api/essaycards/images/scan` is called.
- **Then:** the response is a `500` `ApiError` with `error.code` `IMPORT_INFRA_ERROR`; no partial `imported`/`skipped` report body is returned.

### List images returns a Dataset newest first
- **Given:** the fixture images `fix-img-alpha` and `fix-img-beta`, where `fix-img-beta` has the more recent `created_at`.
- **When:** `GET /api/essaycards/images` is called.
- **Then:** the response is a `Dataset` with `meta.object_type` `"image"`; rows are ordered `fix-img-beta` before `fix-img-alpha`; each row carries `slug`, `source_filename`, `content_type`, `byte_size`, `width`, `height`, `created_at`, and `url` equal to `/api/essaycards/images/<slug>`; no row contains raw image bytes or a `content` field.

### List images is valid when empty
- **Given:** no `essaycards.images` rows.
- **When:** `GET /api/essaycards/images` is called.
- **Then:** the response is a `Dataset` with `rows: []` and `meta.total: 0` — not an error.

### Get image serves bytes with an immutable cache header
- **Given:** an image imported by a scan (row plus processed file present).
- **When:** `GET /api/essaycards/images/{slug}` is called for that slug.
- **Then:** the response is `200`, the body is the processed file's bytes, the `Content-Type` matches the stored `content_type`, and the `Cache-Control` header is `public, max-age=31536000, immutable`.

### Get image with an unknown slug returns 404
- **Given:** no `essaycards.images` row for the slug `does-not-exist`.
- **When:** `GET /api/essaycards/images/does-not-exist` is called.
- **Then:** the response is a `404` `ApiError` with `error.code` `NOT_FOUND`.

### Get image when the row exists but the file is missing returns 404
- **Given:** the fixture image `fix-img-alpha` has a row but no corresponding file in the images directory.
- **When:** `GET /api/essaycards/images/fix-img-alpha` is called.
- **Then:** the response is a `404` `ApiError` with `error.code` `NOT_FOUND` — not a `500`.

### [UI] Review card renders a Markdown image in the answer
- **Given:** a due flashcard whose answer text contains `![diagram](/api/essaycards/images/<slug>)` for a slug that has been imported, and a review session started for that card.
- **When:** the user opens the review session and clicks **Flip**.
- **Then:** the answer area renders an `<img>` element whose `src` resolves to `/api/essaycards/images/<slug>` (the literal Markdown text `![diagram](...)` is not shown), and the rendered image is constrained to the width of the review card (it does not overflow the column).

### [UI — manual] Images view: Copy Markdown button copies the snippet
- **Given:** the Images view at `/essaycards/images` listing at least one imported image.
- **When:** the user clicks the **Copy Markdown** button on an image row.
- **Then:** the clipboard contains exactly `![](/api/essaycards/images/<slug>)` for that row's slug. (Clipboard reads are unreliable under automated browsers; this scenario is verified manually and the test report records it as untested rather than passing.)
