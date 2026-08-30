# Sprint Draft — EssayCards: In-browser image upload (paste / drop / pick)

## Goal

Let the user add an image from the browser while on the EssayCards **Images** view —
by pasting from the clipboard (Ctrl/Cmd-V), dragging a file onto a drop zone, or a
plain file picker — without touching the server-side staging folder. The uploaded
bytes run through the **exact same processing core** Sprint03 built for staged files
(decode + `exif_transpose` + Lanczos downscale + metadata-stripped re-encode + slug +
`source_sha256` idempotency + per-file transaction). The result is identical to a
staged import: a processed file at `/app/images/<slug>.<ext>`, a row in
`essaycards.images`, and a `![](/api/essaycards/images/<slug>)` snippet to copy.

This reverses Sprint03's "Out of Scope: in-app / HTTP upload of image bytes". The two
reasons that exclusion existed are addressed below (threat model; durability).

## Layer / Component

03_Application — EssayCards, Sprint04, building directly on Sprint03_Images
(`essaycards.images` table, `backend/import_images.py` core, `backend/routers/images.py`,
the `/essaycards/images` Images view). Sprint03 is at TESTS_PASSING.

## Decisions locked (from feature review 2026-08-30)

| Question | Decision |
|---|---|
| Durability of an image with no staging original | On upload, the **raw uploaded bytes are written to `/app/images/originals/<source_sha256>.<origext>`** before processing. That subdir is the raw archive of everything uploaded over HTTP. |
| Where originals live | `${DATA_ROOT}/essaycards/images/originals/` — under the already-app-writable `/app/images` mount. **No `compose.yml` change**, no new mount, staging stays `:ro`. |
| Idempotency across both paths | `source_sha256` (SHA-256 of the original uploaded bytes) is the same key `scan_staging` uses. Uploading bytes already imported via staging → `unchanged`, no second row. |
| Editor-inline paste (paste straight into an essay/card textarea) | **Out of scope.** Upload happens on the Images view only; copy-snippet-then-paste stays the bridge. |
| Process | Direct implementation from this draft (`direct_implementer`), no formal design artifacts. |

## Threat model (R-OPS-BP-02)

EssayCards today accepts no bytes over HTTP. This adds one endpoint that does. It stays
`127.0.0.1`-bound behind the shell (`compose.yml:9`), so the surface is "an already-
local caller can submit image bytes for processing", not remote exposure. Required
guards, all in the new endpoint:

- **Hard request-body cap: 12 MiB.** Reject larger with `413` `ApiError`
  (`PAYLOAD_TOO_LARGE`) *before* reading the whole body. 12 MiB = the 5 MiB output
  ceiling plus pre-downscale slack for a large phone photo.
- **Pillow verify before trust.** Open + `Image.verify()` / reload; if it is not a
  real image of an allowed format, `400` `ApiError` `VALIDATION_ERROR` with a
  `reason` matching the Sprint03 skip vocabulary (`not-an-image` / `format-mismatch`).
  Never trust the multipart `Content-Type`.
- **SVG stays rejected** — `image/svg+xml` served same-origin is a stored-XSS vector
  (unchanged from Sprint03). Accept list is exactly Sprint03's:
  `.jpg .jpeg .png .gif .webp`.
- Same `MAX_EDGE` / `JPEG_QUALITY` / `MAX_BYTES` / GIF passthrough rules as Sprint03 —
  reuse the constants, do not redefine.

## Durability model (updates resolved Q2 of Sprint03 / R-CON-BP-03)

Split durable state, both halves owned by EssayCards:

- **Postgres** `essaycards.images` rows — covered by the daily `pg_dump`.
- **`/app/images/<slug>.<ext>`** — processed, web-served bytes. Reproducible.
- **`/app/images/originals/<sha>.<ext>`** — NEW. Raw bytes of every HTTP upload,
  keyed by `source_sha256`. This is the upload path's equivalent of a retained
  staging original.

Neither `/app/images` nor `originals/` is covered by `pg_dump`. The recovery story
after Sprint04:

- Staged images: rebuild `/app/images/*` + rows by re-running `scan_staging` against
  the retained staging folder (unchanged from Sprint03).
- Uploaded images: `originals/` holds the raw bytes keyed by sha; the row carries
  `source_sha256` and `source_filename`. A reprocess-from-`originals/` tool is **out
  of scope** this sprint — `originals/` is the archive that makes such a rebuild
  *possible* later; today it is a manual step (copy an original into staging, rescan).

`CLAUDE.md` "Images" subsection must be updated to describe `originals/` and to keep
the "retain a copy / nothing here is backed up automatically" warning, now covering
both staged and uploaded images.

## Backend

### `backend/import_images.py` — refactor the per-file core to take bytes

Introduce (or reshape `_import_one` into) a bytes-first entry point so scan and upload
share one path:

```
def process_image_bytes(
    conn, *, source_filename: str, raw: bytes, images_dir: Path,
    save_original_dir: Path | None = None,
) -> ImportedImage | Literal["unchanged"] | SkippedFile
```

- `source_sha256 = sha256(raw)`; if a row already has it → return `"unchanged"`
  (do not re-write files, do not insert).
- If `save_original_dir` is not None: `mkdir(parents=True, exist_ok=True)` and write
  `raw` to `save_original_dir / f"{source_sha256}{ext}"` (ext from the sniffed format,
  not the filename). Idempotent — overwrite is fine, bytes are identical.
- Then the existing pipeline: Pillow decode → `exif_transpose` → downscale if
  `max(w,h) > MAX_EDGE` → re-encode metadata-stripped (GIF passthrough per Sprint03
  rules) → reject if still `> MAX_BYTES` → slug from `source_filename` (Sprint03 rule,
  `-<6hex>` on collision) → **`SAVEPOINT` → write `/app/images/<slug>.<ext>` → INSERT
  → `RELEASE` + `conn.commit()`**; on INSERT failure `ROLLBACK TO SAVEPOINT`, unlink
  the processed file (leave the original in `originals/`), return `SkippedFile('error')`.
- `scan_staging` now: for each staging file, read bytes, call `process_image_bytes(...,
  save_original_dir=None)` (staging IS the retained original). Behaviour and its 11
  passing tests must be unchanged.
- `_ensure_in_transaction` (added in Sprint03 fix iteration 1) still guards the first
  `SAVEPOINT` per file.

### `backend/routers/images.py` — new endpoint

```
POST /api/essaycards/images/upload
  Content-Type: multipart/form-data
  fields: file (required, the image), filename (optional, overrides the part filename)
```

- Mutation endpoint (R-CON-BP-04 exempt from Dataset). Success `200` returns a typed
  record: the single image record `{ slug, source_filename, url, width, height,
  byte_size, content_type, created_at, unchanged: bool }`. `unchanged: true` when the
  sha was already present (slug points at the existing row).
- Errors, all `ApiError`: `413 PAYLOAD_TOO_LARGE` (body over cap), `400 VALIDATION_ERROR`
  (not a decodable allowed image / SVG / format-mismatch — include `detail.reason`),
  `500 IMPORT_INFRA_ERROR` (images dir or `originals/` unwritable, or connection-level
  DB failure).
- Effective filename: `filename` field → else the multipart part's filename → else
  `pasted-image` (a clipboard paste usually has no name; slug rule turns
  `pasted-image` → `pasted-image`, then `-<6hex>` per additional paste).
- Uses `save_original_dir = images_dir / "originals"`.
- Reads the body with a running byte cap (don't slurp an unbounded `UploadFile`);
  reject as soon as the cap is exceeded.

### `pyproject.toml`

Add **`python-multipart`** (FastAPI needs it for `UploadFile` / form parsing). Pillow
already added in Sprint03.

### `backend/main.py`

No change — the images router is already registered.

## Frontend — `src/ShellEntry.tsx`, Images view only

One `uploadFiles(files: File[])` helper; three ways to feed it:

1. **Paste:** `onPaste` on the Images-view container — iterate
   `e.clipboardData.files`, keep `type.startsWith('image/')`, call `uploadFiles`.
2. **Drop:** a visible drop zone with `onDragOver` (preventDefault) + `onDrop` reading
   `e.dataTransfer.files`, same filter.
3. **Pick:** `<input type="file" accept="image/*" multiple>` behind a button.

`uploadFiles` POSTs each file as `FormData` (`file`, and `filename` when
`File.name` is meaningful) to `/api/essaycards/images/upload`, collects per-file
results, then re-fetches `GET /api/essaycards/images` and renders the same
imported / unchanged / skipped report block the "Scan staging folder" button already
shows. A large paste of several images uploads them sequentially (simpler error
reporting; volume is tiny).

No new route, no `shellConfig.ts` change. Rebuild (`npx vite build`) + deploy
(`docker cp dist/. atlas-shell:/usr/share/nginx/html/`) after the `.tsx` change.

## Out of scope

- Inline paste into essay/card editor textareas.
- Deleting, replacing, or renaming images.
- A reprocess-from-`originals/` CLI/endpoint.
- Progress bars, chunked/resumable upload, client-side downscale.
- HEIC/HEIF, animated-GIF resize, RAW, PDF, SVG (unchanged from Sprint03).
- Auth (Atlas has none; endpoint is `127.0.0.1`-bound behind the shell).

## Tests — extend `tests/test_images.py` (+ `tests/fixtures.sql` if needed)

`-test` container has no images mount → keep Sprint03's autouse monkeypatch of
`import_images.IMAGES_DIR` / `STAGING_DIR` to `tmp_path`; `originals/` is
`IMAGES_DIR / "originals"` and is created by the code.

- **Upload a valid PNG** → `200`; processed file at `<tmp>/<slug>.png`, original at
  `<tmp>/originals/<sha>.png`, one row, returned record fields correct, `unchanged:false`.
- **Upload bytes whose sha matches an already-imported staged image** → `200`,
  `unchanged:true`, still exactly one row, no second processed file written.
- **Upload a second distinct image with the same filename** → slug gets the `-<6hex>`
  suffix (collision rule holds through the new path).
- **Upload a non-image** (`b"not an image"` as `file`) → `400` `VALIDATION_ERROR`,
  `detail.reason == "not-an-image"`, no row, no files.
- **Upload an `.svg`** → `400` `VALIDATION_ERROR` (rejected before processing).
- **Upload over the 12 MiB body cap** → `413` `PAYLOAD_TOO_LARGE`, no row.
- **Oversized real photo within the cap** (e.g. 2600×1300 JPEG) → `200`, stored image
  downscaled to `MAX_EDGE`, original in `originals/` at full size.
- **`[UI — manual]`** Paste an image onto the Images view → it appears in the list with
  a Copy Markdown button. (No Playwright infra; manual, noted untested.)

All 11 existing Sprint03 `test_images.py` scenarios must still pass unchanged.
