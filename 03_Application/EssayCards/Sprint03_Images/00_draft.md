# Sprint Draft — EssayCards: Images in Essays and Flashcards

## Goal

Let essays and flashcards display images, sourced from a **staging folder on the
server**. The user drops image files into staging by whatever means they like (scp,
a file share, Syncthing); a **batch import** step processes each new file into a
web-suitable form — downscaling oversized phone photos, stripping metadata, giving each
a clean canonical slug regardless of the original filename — and stores the processed
image where the app can serve it. Import hands back a plain Markdown reference
(`![alt](/api/essaycards/images/<slug>)`) to paste into any section's `body_markdown`
or any flashcard's `q` / `a`. Displaying an image is then just "render Markdown", which
essay bodies already do and flashcards do not yet.

## Layer

03_Application

## Component

EssayCards (Sprint03, building on Sprint01_Core + Sprint02_JsonIngestion)

## Decisions locked before design (from draft review)

| Question | Decision |
|---|---|
| Staged file → usable image | **Batch import step** (CLI command + in-app "Scan staging" button, one shared core) |
| Markdown reference scheme | **Cleaned filename slug** (`IMG_1234 (1).JPG` → `img-1234-1`); collision → append short hash |
| Processed image storage | **Disk under `DATA_ROOT`**, with a metadata table in Postgres |
| HEIC/HEIF in staging | **No** — JPG/PNG only; backend needs only Pillow, not `pillow-heif` |

## Scope

### Filesystem layout (compose change)

Two new volume mounts on the `essaycards` service in `compose.yml`:

```yaml
      - ${DATA_ROOT}/essaycards/staging:/app/staging:ro     # user drops files here
      - ${DATA_ROOT}/essaycards/images:/app/images          # processed output, app-writable
```

- `/app/staging` is **read-only** to the container — the app never writes to or deletes
  from staging. The user manages staging themselves.
- `/app/images` holds the processed, web-ready files, named `<slug>.<ext>`.

### Backend — import core (`backend/import_images.py`)

New module, structured like `backend/ingest.py`: a directly-callable function plus a CLI
wrapper. One shared core called by both the CLI and the in-app scan endpoint.

For each file in `/app/staging` (non-recursive) whose extension is
`.jpg/.jpeg/.png/.gif/.webp` (case-insensitive):

1. **Parse** with Pillow. If it does not open as a real image of an allowed format, or
   the declared extension disagrees with the sniffed format, **skip this file** and
   record it in the report — do not abort the batch (per-file resilience, unlike the
   all-or-nothing ingest paths).
2. **Dedupe / idempotency:** `source_sha256` = SHA-256 of the *original* staged bytes.
   If a row with that hash already exists, skip as `unchanged`. Re-running import after
   adding one new file only processes that one file.
3. **Downscale:** if `max(width, height) > MAX_EDGE` (default **2000 px**), resize
   preserving aspect ratio (Lanczos). Never upscale.
4. **Normalize / re-encode:**
   - JPEG → re-encode progressive, quality **82**, all EXIF/metadata dropped.
   - PNG → re-save optimized, metadata dropped.
   - WebP → re-encode, metadata dropped.
   - GIF → passed through byte-for-byte **only if** `byte_size ≤ MAX_BYTES` and
     `max(dim) ≤ MAX_EDGE`; otherwise skipped with reason `gif-too-large`
     (animated-GIF resizing is out of scope).
   - Reject (skip, reason `too-large`) any result still `> MAX_BYTES` (default **5 MiB**).
5. **Slug:** from the original basename — lowercase, drop extension, collapse every run
   of non-`[a-z0-9]` to a single `-`, trim leading/trailing `-`. Empty result →
   `image`. If the slug is already taken by a *different* `source_sha256`, append
   `-` + first 6 hex chars of the hash.
6. **Write** processed bytes to `/app/images/<slug>.<ext>` and `INSERT` the metadata row.

`MAX_EDGE`, `JPEG_QUALITY`, `MAX_BYTES` are module constants (design review decides
whether any need to be env-configurable).

**CLI:** `docker exec atlas-essaycards python -m backend.import_images` — prints a
summary: newly imported (with their final slugs), `unchanged` count, skipped (filename +
reason).

### Backend — endpoints

- `POST /api/essaycards/images/scan` — trigger the import core (no request body).
  Mutation endpoint (R-CON-BP-04 exempt from Dataset); returns a **typed record**:
  ```json
  { "imported": [ { "slug": "img-1234-1", "source_filename": "IMG_1234 (1).JPG",
                    "url": "/api/essaycards/images/img-1234-1",
                    "width": 2000, "height": 1500, "byte_size": 380221 } ],
    "unchanged": 4,
    "skipped": [ { "filename": "notes.txt", "reason": "not-an-image" } ] }
  ```
  `ApiError` on infrastructure failure only (staging dir unreadable, images dir
  unwritable). Per-file problems are `skipped` entries, not errors.
- `GET /api/essaycards/images/{slug}` — serves the processed file from `/app/images`
  with its stored `Content-Type` and `Cache-Control: public, max-age=31536000, immutable`
  (a slug's bytes never change; a re-imported different image gets a different slug).
  **Deliberately not a Dataset** — a binary asset for an `<img>` tag, the same
  R-CON-BP-04 carve-out already documented for `GET /essays/{id}/examination-package`
  in `backend/routers/examinations.py`. The new router docstring must state this.
  `404` `ApiError` `NOT_FOUND` if the slug is unknown or its file is missing on disk.
- `GET /api/essaycards/images` — read endpoint, returns a **Dataset**
  (`slug`, `source_filename`, `content_type`, `byte_size`, `width`, `height`,
  `created_at`, `url`; never the bytes). Ordered `created_at desc`. Empty result valid.
  Same read-vs-mutation split precedent as `GET /sections/{id}/examinations` (Dataset)
  beside the export endpoint (not a Dataset).

### Backend — ingestion paths

**No change to either ingestion path.** Image references are ordinary Markdown text in
`body_markdown` / `q` / `a`; the markdown CLI (`backend/ingest.py`) and the JSON endpoint
(`backend/routers/essays.py`) already pass those strings through untouched. Document the
new workflow in `CLAUDE.md` "Content ingestion": import images first, then reference
their slugs in essay/card text.

### Frontend

- **Flashcard review UI** (`ReviewSessionView`, `src/ShellEntry.tsx`): render
  `current.question` and `current.answer` through `ReactMarkdown` instead of bare text
  (`ShellEntry.tsx:478`, `:481`). This is the only change that makes card images
  possible at all; it also gives cards the same Markdown formatting essay bodies have.
- **Essay reader** (`ReaderView`): already renders `body_markdown` via `ReactMarkdown`
  with no plugins — `![](...)` already works. Only add CSS `img { max-width: 100%;
  height: auto }` under `.essaycards-section-body` and the review card so a large image
  can't blow out the 720 px column.
- **New "Images" view** at `/essaycards/images`, reachable from a button on the essay
  list:
  - "Scan staging folder" button → `POST /images/scan`, then shows the returned report
    (newly imported slugs, unchanged count, skipped files + reasons).
  - Lists imported images (`GET /api/essaycards/images`) as thumbnails with their
    original filename, dimensions/size, and a "Copy Markdown" button that copies
    `![](/api/essaycards/images/<slug>)`.
  - This view is the bridge: scan → copy snippet → paste into the "Add / Update Essay"
    JSON, an offline markdown file, or a card's q/a.
- No rich-text editor, no drag-and-drop, no in-browser upload — files reach the server
  through the staging folder, out of band.

## Out of Scope

- **In-app / HTTP upload of image bytes.** Files arrive via the staging folder only.
- **Deleting images / cleanup.** An image row + its `/app/images` file is never removed
  by this sprint. An imported image that is never referenced just sits there; a
  reference to a slug that was never imported renders a broken image (exactly as a bad
  `#anchor_slug` "jump to passage" link already does nothing). Same accepted-gap style
  as Sprint01's "deleting a section from the source does not delete its row".
- **Re-processing already-imported images** when `MAX_EDGE`/quality constants change.
  Import is keyed on `source_sha256`; a once-imported file is never touched again. To
  re-process, the user would remove the row/file (no tooling for that this sprint).
- **SVG.** `image/svg+xml` served same-origin is a stored-XSS vector (R-OPS-BP-02).
  Not an accepted extension.
- **HEIC/HEIF**, animated-GIF resizing, RAW formats, PDF.
- **EXIF-based auto-rotation** beyond what Pillow's `ImageOps.exif_transpose` does in
  the normalize step (that one call is in scope; anything fancier is not).
- Authentication. Atlas has no per-app auth; every component binds `127.0.0.1` behind
  the shell (`compose.yml:9`). `POST /images/scan` adds an HTTP-reachable trigger for a
  filesystem+DB operation on that already-reachable surface — called out per
  R-OPS-BP-02. It reads a read-only mount and writes only to the app's own images dir;
  it accepts no file content over HTTP, so the attack surface is "can cause a rescan",
  not "can inject bytes".

## Data Model

New table only; no change to `essays`, `essay_sections`, `flashcards`,
`flashcard_review_state`, `section_examinations`.

```sql
create table if not exists essaycards.images (
    slug            text        primary key,
    stored_filename text        not null,          -- e.g. 'img-1234-1.jpg', relative to /app/images
    content_type    text        not null,
    byte_size       integer     not null,
    width           integer,                       -- null only for pass-through GIF if undecodable
    height          integer,
    source_sha256   text        not null,
    source_filename text        not null,          -- original staged name, for the Images list view
    created_at      timestamptz not null default now(),
    constraint uq_images_source_sha256 unique (source_sha256),
    constraint ck_images_content_type
        check (content_type in ('image/png','image/jpeg','image/gif','image/webp')),
    constraint ck_images_byte_size check (byte_size > 0 and byte_size <= 5242880)
);
```

- **Durable state is split (R-CON-BP-03):** metadata rows in Postgres, processed bytes
  in `/app/images` on the `DATA_ROOT` volume. Both owned by EssayCards. The two must
  stay consistent — `GET /images/{slug}` 404s (not 500s) if the row exists but the file
  is gone, and import is transactional per file (write file, then insert row; on insert
  failure, unlink the file).
- **Backup model (resolved — Q2):** `/app/images` is **not** covered by the daily
  `pg_dump` (`02_Platform/Postgres/atlas_*.dump`), and by design nothing else backs it
  up either. The **staging originals are the source of truth**; the staging originals
  plus a re-run of import fully reconstruct both `/app/images` and the metadata rows.
  This matches the existing `${DATA_ROOT}/essaycards/content:ro` precedent. The
  `essaycards.images` schema comment and a new `CLAUDE.md` "Images" subsection must
  both state plainly that the user must retain their staging originals.

## API — Query Behavior Explicitness (R-CON-AL-01)

### `GET /api/essaycards/images`
- Parameters: none. Ordering: `created_at desc`. Grouping: none. Time basis: server.
- Empty result valid (`rows: []`, `meta.total: 0`). `meta.object_type: "image"`.
- Bytes (`content`) never included — metadata + `url` only.

### `POST /api/essaycards/images/scan`
- No body. Idempotent: safe to call repeatedly; only new (unseen `source_sha256`) files
  are processed.
- `200` with the typed report record (see Scope). `ApiError` only for staging-dir
  unreadable / images-dir unwritable.

### `GET /api/essaycards/images/{slug}`
- Path param `slug`. No query params.
- `200`: processed bytes, stored `Content-Type`, immutable `Cache-Control`.
- `404` `ApiError` `NOT_FOUND`: unknown slug, or row exists but file missing.
- Not a Dataset — documented R-CON-BP-04 exemption (binary asset for `<img>`).

## Rendering Safety

- `ReactMarkdown` is used **without `rehype-raw`** in the reader and (newly) the review
  card — raw HTML in `body_markdown` / `q` / `a` stays inert. Do not add `rehype-raw`.
- `react-markdown` v8+ sanitizes `![]()` / `[]()` URIs by default (`javascript:` etc.
  dropped). No custom `urlTransform`; do not disable the default.
- `img` sizing is CSS-only — no custom `img` component override.

## UI round-trip (R-CON-AL-05)

Images are not an editable field on any record — they are literal text inside existing
Markdown fields whose round-trip Sprint01/02 already defined. The only new interactive
surface is the "Scan staging folder" trigger, which takes no user input and has no
clear/null state. Nothing new to design there.

## Dependencies

- Add **`Pillow`** to `pyproject.toml` (`backend` deps). No `pillow-heif`.

## Resolved Design Questions (from draft review, 2026-08-30)

All six open questions were resolved before design. The design phase implements these
decisions; it does not re-open them.

1. **Constants confirmed as-is:** `MAX_EDGE = 2000`, `JPEG_QUALITY = 82`,
   `MAX_BYTES = 5 * 1024 * 1024` (5 MiB), accept list `.jpg/.jpeg/.png/.gif/.webp`.
   These are **module-level constants in `backend/import_images.py`** — not
   `config.env` entries. `MAX_EDGE` (2000 px) covers the 720 px reading column at 2×
   DPI with headroom; `JPEG_QUALITY` 82 is the standard good default; `MAX_BYTES`
   5 MiB is generous post-downscale. `MAX_BYTES` is one decision shared with the
   `ck_images_byte_size` CHECK in `10_schema.sql` — the two must change together
   (already noted in the schema comment).
2. **Durability — staging originals are the source of truth.** `/app/images` is
   treated as **reproducible cache-like state**: fully reconstructable by re-running
   import against the retained staging originals. Atlas does **not** back it up, by
   design — this matches the existing `${DATA_ROOT}/essaycards/content:ro` precedent
   (a user-managed durable source under `DATA_ROOT` that the daily `pg_dump` does not
   cover). Adding a `DATA_ROOT` archive is a separate platform concern, out of scope
   here. **The design must state this explicitly in two places:** the
   `essaycards.images` schema comment (durable-state split, R-CON-BP-03) and a new
   `CLAUDE.md` "Images" subsection ("keep your staging originals — `/app/images` is
   rebuilt from them, never backed up").
3. **Keep both the CLI and the in-app `POST /images/scan` endpoint**, over one shared
   import core (as drafted). The Images view depends on the endpoint as the
   scan→copy→paste workflow bridge. R-OPS-BP-02: the added surface is only "can
   trigger a rescan" on a service already bound to `127.0.0.1` behind the shell; no
   image bytes are accepted over HTTP.
4. **`GET /images/{slug}` uses a plain `FileResponse`.** No streaming, no manual range
   handling — Starlette's `FileResponse` covers content-type and range requests for
   ≤5 MiB assets.
5. **Slug-collision suffix: first 6 hex chars of `source_sha256`.** Deterministic, no
   counter state; a same-basename + different-`source_sha256` + matching-6-hex
   collision is not a real risk for a personal corpus.
6. **UI test coverage:** `10_test_spec.md` must include exactly one required `[UI]`
   scenario — **"review card renders a Markdown image in the answer"** (the only
   genuinely new UI behavior; the essay reader already renders `![]()`). A second
   scenario, "Images view: Copy Markdown button copies the snippet", is included as
   `[UI — manual]` only (clipboard assertions are unreliable under Playwright) and the
   test report notes it as untested rather than passing.
